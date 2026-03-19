"""
scripts/train_lstm.py
Módulo 4 — Soft Computing / LSTM

Genera 35 perfiles de tormenta sintéticos usando las curvas Huff y el
modelo físico Manning ya implementados en el proyecto, entrena una red
LSTM y evalúa el rendimiento mediante MSE.

Uso:
    # Desde la raíz del scenario-engine
    python scripts/train_lstm.py

    # Solo evaluar un modelo ya entrenado
    python scripts/train_lstm.py --eval-only

    # Cambiar épocas o tamaño de ventana
    python scripts/train_lstm.py --epochs 100 --window 12

Salida:
    app/core/lstm_model/fluvi_lstm.keras   ← modelo listo para inferencia
    app/core/lstm_model/scaler.json        ← parámetros de normalización
    app/core/lstm_model/training_report.json ← MSE + métricas por perfil

Dependencias:
    pip install tensorflow numpy
    (el resto del proyecto ya está en requirements.txt)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import numpy as np

# ── Asegurar que el módulo app/ sea importable ────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent.parent   # app/scripts/ → app/ → scenario-engine/
sys.path.insert(0, str(ROOT))

from app.core.hydrology import (
    build_rain_profile,
    compute_water_level,
    DistributionModel,
    HuffQuartile,
)
from app.core.state import SimConfig, TerrainCell
from app.core.lstm_predictor import (
    LSTMPredictor,
    MinMaxScaler,
    MODEL_DIR,
    MODEL_PATH,
    SCALER_PATH,
    WINDOW_SIZE,
    FEATURE_DIM,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("train_lstm")


# ══════════════════════════════════════════════════════════════════════════════
# 1. Definición de los 35 perfiles de tormenta
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class StormProfile:
    """Parámetros de un evento de tormenta para generar datos de entrenamiento."""
    intensity_mm_h: float
    duration_hours: int
    duration_minutes: int
    distribution: DistributionModel
    huff_quartile: HuffQuartile
    infiltration_rate: float   = 12.5
    runoff_coefficient: float  = 0.65
    manning_n: float           = 0.035
    label: str                 = ""


def build_35_profiles() -> list[StormProfile]:
    """
    35 perfiles cubriendo el espacio paramétrico completo del sistema:
    - 4 cuartiles Huff × variedad de intensidades y duraciones
    - Distribución uniforme para contraste
    - Variantes de parámetros hidráulicos (infiltración alta/baja, Manning)

    Diseño basado en rangos realistas para cuencas tropicales mexicanas.
    """
    profiles: list[StormProfile] = []

    # ── Grupo A: Tormentas Huff Q1 (pico temprano) — 8 perfiles ──────────────
    for intensity, hours in [(20, 1), (40, 2), (60, 1), (80, 3),
                             (100, 2), (130, 1), (160, 2), (200, 1)]:
        profiles.append(StormProfile(
            intensity_mm_h=intensity, duration_hours=hours,
            duration_minutes=0, distribution=DistributionModel.gaussian,
            huff_quartile=HuffQuartile.Q1,
            label=f"Q1_i{intensity}_h{hours}",
        ))

    # ── Grupo B: Tormentas Huff Q2 (pico segundo cuarto) — 8 perfiles ────────
    for intensity, hours, mins in [(30, 1, 30), (55, 2, 0), (75, 2, 30),
                                   (90, 3, 0), (110, 1, 0), (140, 2, 0),
                                   (170, 1, 30), (190, 3, 0)]:
        profiles.append(StormProfile(
            intensity_mm_h=intensity, duration_hours=hours,
            duration_minutes=mins, distribution=DistributionModel.gaussian,
            huff_quartile=HuffQuartile.Q2,
            label=f"Q2_i{intensity}_h{hours}m{mins}",
        ))

    # ── Grupo C: Tormentas Huff Q3 (pico tardío) — 6 perfiles ────────────────
    for intensity, hours in [(45, 2), (85, 3), (120, 2), (155, 3),
                             (175, 2), (195, 4)]:
        profiles.append(StormProfile(
            intensity_mm_h=intensity, duration_hours=hours,
            duration_minutes=0, distribution=DistributionModel.gaussian,
            huff_quartile=HuffQuartile.Q3,
            label=f"Q3_i{intensity}_h{hours}",
        ))

    # ── Grupo D: Tormentas Huff Q4 (pico muy tardío) — 5 perfiles ─────────────
    for intensity, hours in [(50, 3), (95, 4), (135, 3), (165, 5), (200, 4)]:
        profiles.append(StormProfile(
            intensity_mm_h=intensity, duration_hours=hours,
            duration_minutes=0, distribution=DistributionModel.gaussian,
            huff_quartile=HuffQuartile.Q4,
            label=f"Q4_i{intensity}_h{hours}",
        ))

    # ── Grupo E: Distribución uniforme — 4 perfiles ───────────────────────────
    for intensity, hours in [(25, 2), (70, 3), (115, 2), (180, 1)]:
        profiles.append(StormProfile(
            intensity_mm_h=intensity, duration_hours=hours,
            duration_minutes=0, distribution=DistributionModel.uniform,
            huff_quartile=HuffQuartile.Q2,   # ignorado en uniforme
            label=f"UNI_i{intensity}_h{hours}",
        ))

    # ── Grupo F: Variantes hidráulicas (suelo impermeable / forestal) — 4 ─────
    hydraulic_variants = [
        # Suelo urbano impermeable — escorrentía alta, infiltración baja
        (100, 2, HuffQuartile.Q1, 3.0,  0.90, 0.015, "urban_imperm"),
        # Suelo forestal — infiltración alta, escorrentía baja
        (100, 2, HuffQuartile.Q1, 25.0, 0.35, 0.060, "forest_perm"),
        # Suelo agrícola seco
        (80,  3, HuffQuartile.Q2, 8.0,  0.70, 0.030, "agri_dry"),
        # Suelo agrícola saturado (post-tormenta previa)
        (80,  3, HuffQuartile.Q2, 2.0,  0.85, 0.025, "agri_sat"),
    ]
    for intensity, hours, quartile, infil, runoff, manning, lbl in hydraulic_variants:
        profiles.append(StormProfile(
            intensity_mm_h=intensity, duration_hours=hours,
            duration_minutes=0, distribution=DistributionModel.gaussian,
            huff_quartile=quartile,
            infiltration_rate=infil, runoff_coefficient=runoff, manning_n=manning,
            label=lbl,
        ))

    assert len(profiles) == 35, f"Se esperaban 35 perfiles, hay {len(profiles)}"
    return profiles


# ══════════════════════════════════════════════════════════════════════════════
# 2. Generador de datos de entrenamiento
# ══════════════════════════════════════════════════════════════════════════════

# Celda de terreno representativa (elevación media de cuenca)
_CELL = TerrainCell(id="training-cell", elevation=5.0)


async def _simulate_profile(profile: StormProfile) -> tuple[list[float], list[float]]:
    """
    Corre el modelo físico sobre un perfil y devuelve:
        intensities: serie temporal de intensidad (mm/h)
        levels:      nivel de agua resultante por paso (m)
    """
    rain = build_rain_profile(
        intensity_mm_h=profile.intensity_mm_h,
        duration_hours=profile.duration_hours,
        duration_minutes=profile.duration_minutes,
        distribution=profile.distribution,
        huff_quartile=profile.huff_quartile,
        resolution_sec=300,   # pasos de 5 min → balance densidad / memoria
    )

    config = SimConfig(
        infiltration_rate=profile.infiltration_rate,
        runoff_coefficient=profile.runoff_coefficient,
        manning_n=profile.manning_n,
    )

    levels: list[float] = []
    for intensity in rain.intensities_mm_h:
        result = await compute_water_level(_CELL, intensity, config)
        levels.append(result.water_level)

    return rain.intensities_mm_h, levels


def generate_training_data(
    profiles: list[StormProfile],
    window_size: int,
) -> tuple[np.ndarray, np.ndarray, MinMaxScaler]:
    """
    Para cada perfil genera secuencias (X, y) con ventana deslizante:
        X shape: (N, window_size, 1)  ← ventana de intensidades normalizadas
        y shape: (N, 1)               ← nivel de agua normalizado

    Retorna también el scaler ajustado a los datos.
    """
    log.info("Generando %d perfiles de tormenta con Manning...", len(profiles))
    t0 = time.time()

    all_intensities: list[list[float]] = []
    all_levels:      list[list[float]] = []

    for i, profile in enumerate(profiles):
        intensities, levels = asyncio.run(_simulate_profile(profile))
        all_intensities.append(intensities)
        all_levels.append(levels)
        log.info(
            "  [%2d/35] %-25s  pasos=%3d  peak_level=%.4f m",
            i + 1, profile.label, len(levels), max(levels) if levels else 0,
        )

    elapsed = time.time() - t0
    log.info("Simulación completada en %.1f s", elapsed)

    # ── Ajustar scaler sobre todos los datos ──────────────────────────────────
    flat_intensities = [v for seq in all_intensities for v in seq]
    flat_levels      = [v for seq in all_levels      for v in seq]

    scaler = MinMaxScaler(
        x_min=0.0,
        x_max=max(flat_intensities) * 1.05,   # 5% margen para evitar saturación
        y_min=0.0,
        y_max=max(flat_levels)      * 1.10,
    )
    log.info(
        "Scaler: intensity [%.1f, %.1f] mm/h | level [%.4f, %.4f] m",
        scaler.x_min, scaler.x_max, scaler.y_min, scaler.y_max,
    )

    # ── Construir ventanas deslizantes ────────────────────────────────────────
    X_list: list[np.ndarray] = []
    y_list: list[float]      = []

    for intensities, levels in zip(all_intensities, all_levels):
        n = len(intensities)
        for t in range(window_size, n):
            window = intensities[t - window_size : t]
            X_list.append(
                np.array([[scaler.scale_x(v)] for v in window], dtype=np.float32)
            )
            y_list.append(scaler.scale_y(levels[t]))

    X = np.stack(X_list)           # (N, window_size, 1)
    y = np.array(y_list, dtype=np.float32).reshape(-1, 1)

    log.info(
        "Dataset: %d secuencias  X%s  y%s",
        len(X), X.shape, y.shape,
    )
    return X, y, scaler


# ══════════════════════════════════════════════════════════════════════════════
# 3. Construcción del modelo LSTM
# ══════════════════════════════════════════════════════════════════════════════

def build_lstm_model(window_size: int, feature_dim: int):
    """
    Arquitectura:
        Input(window_size, feature_dim)
        → LSTM(64, return_sequences=True)
        → Dropout(0.2)
        → LSTM(32)
        → Dense(16, relu)
        → Dense(1, sigmoid)    ← salida normalizada [0,1]

    La puerta de olvido implementa:
        f_t = σ(W_f · [h_{t-1}, x_t] + b_f)
    Lo que se traduce en que el modelo aprende cuánta "memoria de lluvia
    previa" es relevante para el nivel actual — exactamente la inercia
    hidráulica que Manning ignora.
    """
    import keras
    from keras import layers

    model = keras.Sequential(
        [
            keras.Input(shape=(window_size, feature_dim)),

            # Primera capa LSTM: captura patrones de largo plazo
            # return_sequences=True para alimentar la segunda capa
            layers.LSTM(64, return_sequences=True, name="lstm_1"),
            layers.Dropout(0.2, name="dropout_1"),

            # Segunda capa LSTM: condensa en vector de contexto
            layers.LSTM(32, return_sequences=False, name="lstm_2"),

            # Capas densas de decodificación
            layers.Dense(16, activation="relu", name="dense_1"),
            layers.Dense(1,  activation="sigmoid", name="output"),
        ],
        name="fluvi_lstm",
    )

    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=1e-3),
        loss="mse",
        metrics=["mae"],
    )

    return model


# ══════════════════════════════════════════════════════════════════════════════
# 4. Entrenamiento
# ══════════════════════════════════════════════════════════════════════════════

def train(
    X: np.ndarray,
    y: np.ndarray,
    scaler: MinMaxScaler,
    epochs: int,
    window_size: int,
    feature_dim: int,
) -> dict:
    """
    Entrena el modelo, guarda en disco y retorna el reporte de métricas.
    """
    import keras

    # ── Split 80/20 ───────────────────────────────────────────────────────────
    split     = int(len(X) * 0.8)
    X_train, X_val = X[:split], X[split:]
    y_train, y_val = y[:split], y[split:]

    log.info(
        "Split → train=%d  val=%d  (80/20)",
        len(X_train), len(X_val),
    )

    model = build_lstm_model(window_size, feature_dim)
    model.summary(print_fn=log.info)

    callbacks = [
        keras.callbacks.EarlyStopping(
            monitor="val_loss",
            patience=15,
            restore_best_weights=True,
            verbose=1,
        ),
        keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss",
            factor=0.5,
            patience=7,
            min_lr=1e-6,
            verbose=1,
        ),
    ]

    log.info("Iniciando entrenamiento  epochs=%d  batch=32", epochs)
    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=epochs,
        batch_size=32,
        callbacks=callbacks,
        verbose=1,
    )

    # ── Evaluación MSE ────────────────────────────────────────────────────────
    y_pred_scaled = model.predict(X_val, verbose=0).flatten()
    y_true_scaled = y_val.flatten()

    # Desnormalizar para MSE en metros
    y_pred_m = np.array([scaler.inverse_y(float(v)) for v in y_pred_scaled])
    y_true_m = np.array([scaler.inverse_y(float(v)) for v in y_true_scaled])

    mse_scaled = float(np.mean((y_pred_scaled - y_true_scaled) ** 2))
    mse_meters = float(np.mean((y_pred_m - y_true_m) ** 2))
    mae_meters = float(np.mean(np.abs(y_pred_m - y_true_m)))
    rmse_meters = float(np.sqrt(mse_meters))

    log.info("── Evaluación final ──────────────────────────────────────")
    log.info("  MSE  (normalizado): %.6f", mse_scaled)
    log.info("  MSE  (metros²):     %.6f", mse_meters)
    log.info("  RMSE (metros):      %.6f m", rmse_meters)
    log.info("  MAE  (metros):      %.6f m", mae_meters)
    log.info("─────────────────────────────────────────────────────────")

    # ── Persistencia ──────────────────────────────────────────────────────────
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    model.save(MODEL_PATH)
    log.info("Modelo guardado → %s", MODEL_PATH)

    SCALER_PATH.write_text(json.dumps(scaler.to_dict(), indent=2))
    log.info("Scaler guardado → %s", SCALER_PATH)

    # ── Reporte JSON ──────────────────────────────────────────────────────────
    report = {
        "training_samples":   int(len(X_train)),
        "validation_samples": int(len(X_val)),
        "epochs_run":         int(len(history.history["loss"])),
        "final_train_loss":   float(history.history["loss"][-1]),
        "final_val_loss":     float(history.history["val_loss"][-1]),
        "mse_normalized":     mse_scaled,
        "mse_meters_sq":      mse_meters,
        "rmse_meters":        rmse_meters,
        "mae_meters":         mae_meters,
        "window_size":        window_size,
        "scaler":             scaler.to_dict(),
        "architecture": {
            "layers":    ["LSTM(64)", "Dropout(0.2)", "LSTM(32)", "Dense(16,relu)", "Dense(1,sigmoid)"],
            "optimizer": "Adam(lr=1e-3)",
            "loss":      "MSE",
            "forget_gate": "f_t = σ(W_f · [h_{t-1}, x_t] + b_f)",
        },
    }

    report_path = MODEL_DIR / "training_report.json"
    report_path.write_text(json.dumps(report, indent=2))
    log.info("Reporte guardado → %s", report_path)

    return report


# ══════════════════════════════════════════════════════════════════════════════
# 5. Evaluación por perfil (35 perfiles vs. predicción LSTM)
# ══════════════════════════════════════════════════════════════════════════════

def evaluate_per_profile(
    profiles: list[StormProfile],
    predictor: LSTMPredictor,
    window_size: int,
) -> list[dict]:
    """
    Para cada uno de los 35 perfiles:
    - Corre el modelo físico para obtener niveles reales (ground truth)
    - Usa el predictor LSTM para predecir paso a paso
    - Calcula MSE individual
    - Registra dónde difiere más (inercia post-tormenta)

    Retorna lista de dicts con métricas por perfil.
    """
    log.info("Evaluando 35 perfiles individualmente...")
    results = []

    for i, profile in enumerate(profiles):
        intensities, levels_physical = asyncio.run(_simulate_profile(profile))

        predictor.reset_window()
        levels_lstm: list[Optional[float]] = []

        for intensity in intensities:
            predictor.push(intensity)
            pred = predictor.predict()
            levels_lstm.append(pred)

        # Filtrar pasos donde LSTM tiene ventana completa
        valid_pairs = [
            (levels_physical[t], levels_lstm[t])
            for t in range(window_size, len(levels_physical))
            if levels_lstm[t] is not None
        ]

        if not valid_pairs:
            log.warning("  [%2d] %s — sin predicciones válidas", i + 1, profile.label)
            continue

        y_true = np.array([p[0] for p in valid_pairs])
        y_pred = np.array([p[1] for p in valid_pairs])

        mse  = float(np.mean((y_pred - y_true) ** 2))
        mae  = float(np.mean(np.abs(y_pred - y_true)))
        peak_physical = float(np.max(y_true))
        peak_lstm     = float(np.max(y_pred))
        peak_error    = abs(peak_lstm - peak_physical)

        result = {
            "profile":         profile.label,
            "steps":           len(y_true),
            "mse_m2":          round(mse, 6),
            "mae_m":           round(mae, 6),
            "peak_physical_m": round(peak_physical, 4),
            "peak_lstm_m":     round(peak_lstm, 4),
            "peak_error_m":    round(peak_error, 4),
        }
        results.append(result)

        log.info(
            "  [%2d/35] %-25s  MSE=%.6f  MAE=%.4f m  peak_err=%.4f m",
            i + 1, profile.label, mse, mae, peak_error,
        )

    # Resumen agregado
    all_mse = [r["mse_m2"] for r in results]
    log.info("── Resumen 35 perfiles ───────────────────────────────────")
    log.info("  MSE promedio:  %.6f m²", np.mean(all_mse))
    log.info("  MSE mínimo:    %.6f m²  (%s)", np.min(all_mse),  results[np.argmin(all_mse)]["profile"])
    log.info("  MSE máximo:    %.6f m²  (%s)", np.max(all_mse),  results[np.argmax(all_mse)]["profile"])
    log.info("─────────────────────────────────────────────────────────")

    return results


# ══════════════════════════════════════════════════════════════════════════════
# 6. Entry point
# ══════════════════════════════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fluvi LSTM Trainer — Módulo 4")
    p.add_argument("--epochs",    type=int,  default=80,
                   help="Épocas máximas de entrenamiento (default: 80)")
    p.add_argument("--window",    type=int,  default=WINDOW_SIZE,
                   help=f"Tamaño de ventana temporal (default: {WINDOW_SIZE})")
    p.add_argument("--eval-only", action="store_true",
                   help="Solo evaluar modelo ya entrenado (no reentrenar)")
    return p.parse_args()


def main() -> None:
    args  = parse_args()
    w     = args.window

    profiles = build_35_profiles()
    log.info("35 perfiles de tormenta definidos")

    if not args.eval_only:
        # ── Generar datos + entrenar ──────────────────────────────────────────
        X, y, scaler = generate_training_data(profiles, window_size=w)
        report = train(X, y, scaler, epochs=args.epochs, window_size=w, feature_dim=FEATURE_DIM)

        log.info(
            "Entrenamiento completado — MSE final: %.6f m²  RMSE: %.4f m",
            report["mse_meters_sq"], report["rmse_meters"],
        )
    else:
        log.info("--eval-only: saltando entrenamiento")

    # ── Evaluación por perfil ─────────────────────────────────────────────────
    predictor = LSTMPredictor()
    if not predictor.load():
        log.error("No se encontró modelo entrenado. Corre sin --eval-only primero.")
        sys.exit(1)

    per_profile = evaluate_per_profile(profiles, predictor, window_size=w)

    # Guardar resultados por perfil junto al reporte
    per_profile_path = MODEL_DIR / "per_profile_mse.json"
    per_profile_path.write_text(json.dumps(per_profile, indent=2))
    log.info("MSE por perfil guardado → %s", per_profile_path)

    log.info("Módulo 4 completado exitosamente.")


if __name__ == "__main__":
    main()