"""
app/core/lstm_predictor.py
Módulo 4 — Soft Computing / LSTM

Predice el nivel de agua (m) a partir de la secuencia temporal de
lluvia acumulada usando una Red Neuronal Recurrente con puertas LSTM.

Arquitectura:
  Input  → LSTM(64) → Dropout(0.2) → LSTM(32) → Dense(1)

Puerta de olvido (forget gate):
  f_t = σ(W_f · [h_{t-1}, x_t] + b_f)

La dependencia temporal captura la inercia del agua que el modelo
físico Manning ignora (el suelo saturado retiene memoria de lluvia
previa varias horas después del evento).

Uso:
  predictor = LSTMPredictor()
  predictor.load()                  # carga modelo entrenado desde disco
  level = predictor.predict(window) # window: list[float] de intensidades mm/h
"""

import os
import json
import logging
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constantes ────────────────────────────────────────────────────────────────
MODEL_DIR       = Path(__file__).parent / "lstm_model"
MODEL_PATH      = MODEL_DIR / "fluvi_lstm.keras"
SCALER_PATH     = MODEL_DIR / "scaler.json"
WINDOW_SIZE     = 12        # pasos de 5 min → ventana de 1 hora
FEATURE_DIM     = 1         # entrada: intensidad mm/h (escalar por paso)


# ── Scaler manual (evita dependencia sklearn en producción) ───────────────────

@dataclass
class MinMaxScaler:
    """Normaliza y desnormaliza entre [0, 1]."""
    x_min: float = 0.0
    x_max: float = 200.0   # intensidad máxima del sistema (mm/h)
    y_min: float = 0.0
    y_max: float = 5.0     # nivel máximo esperado (m)

    def scale_x(self, val: float) -> float:
        r = self.x_max - self.x_min
        return (val - self.x_min) / r if r > 0 else 0.0

    def scale_y(self, val: float) -> float:
        r = self.y_max - self.y_min
        return (val - self.y_min) / r if r > 0 else 0.0

    def inverse_y(self, val: float) -> float:
        return val * (self.y_max - self.y_min) + self.y_min

    def to_dict(self) -> dict:
        return {
            "x_min": self.x_min, "x_max": self.x_max,
            "y_min": self.y_min, "y_max": self.y_max,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MinMaxScaler":
        return cls(**d)


# ── Predictor ─────────────────────────────────────────────────────────────────

class LSTMPredictor:
    """
    Wrapper del modelo LSTM para predicción en línea durante simulaciones.

    El modelo acepta una ventana deslizante de WINDOW_SIZE pasos de
    intensidad de lluvia (mm/h) y predice el nivel de agua resultante (m).

    Si el modelo no está entrenado, predict() devuelve None y el sistema
    usa el modelo físico Manning como fallback transparente.
    """

    def __init__(self) -> None:
        self._model   = None          # keras.Model | None
        self._scaler  = MinMaxScaler()
        self._ready   = False
        self._window: list[float] = []   # buffer circular de intensidades

    # ── Ciclo de vida ─────────────────────────────────────────────────────────

    def load(self) -> bool:
        """
        Carga modelo y scaler desde disco.
        Retorna True si se cargó correctamente, False si no existe.
        """
        try:
            import keras  # importación tardía — opcional en entorno sin GPU
        except ImportError:
            logger.warning("[LSTM] keras no disponible — predictor deshabilitado")
            return False

        if not MODEL_PATH.exists():
            logger.info("[LSTM] Modelo no entrenado aún — usando Manning como fallback")
            return False

        try:
            self._model  = keras.models.load_model(MODEL_PATH)
            if SCALER_PATH.exists():
                self._scaler = MinMaxScaler.from_dict(
                    json.loads(SCALER_PATH.read_text())
                )
            self._ready = True
            logger.info(f"[LSTM] Modelo cargado desde {MODEL_PATH}")
            return True
        except Exception as e:
            logger.error(f"[LSTM] Error cargando modelo: {e}")
            return False

    @property
    def is_ready(self) -> bool:
        return self._ready

    # ── Ventana deslizante ────────────────────────────────────────────────────

    def push(self, intensity_mm_h: float) -> None:
        """Agrega una lectura a la ventana. Mantiene tamaño = WINDOW_SIZE."""
        self._window.append(intensity_mm_h)
        if len(self._window) > WINDOW_SIZE:
            self._window.pop(0)

    def reset_window(self) -> None:
        self._window = []

    # ── Predicción ────────────────────────────────────────────────────────────

    def predict(self, window: Optional[list[float]] = None) -> Optional[float]:
        """
        Predice el nivel de agua dado una ventana de intensidades.

        Args:
            window: lista de WINDOW_SIZE intensidades (mm/h).
                    Si None, usa el buffer interno actualizado con push().

        Returns:
            nivel predicho en metros, o None si el modelo no está listo
            o la ventana es insuficiente.
        """
        if not self._ready or self._model is None:
            return None

        seq = window if window is not None else self._window

        if len(seq) < WINDOW_SIZE:
            # Ventana insuficiente — rellenar con ceros al inicio
            seq = [0.0] * (WINDOW_SIZE - len(seq)) + list(seq)

        # Normalizar y construir tensor (1, WINDOW_SIZE, 1)
        scaled = np.array(
            [[self._scaler.scale_x(v)] for v in seq],
            dtype=np.float32,
        ).reshape(1, WINDOW_SIZE, FEATURE_DIM)

        try:
            pred_scaled = float(self._model.predict(scaled, verbose=0)[0][0])
            level = self._scaler.inverse_y(pred_scaled)
            return round(max(0.0, level), 4)
        except Exception as e:
            logger.error(f"[LSTM] Error en predicción: {e}")
            return None


# ── Singleton compartido por toda la aplicación ───────────────────────────────
_predictor: Optional[LSTMPredictor] = None


def get_predictor() -> LSTMPredictor:
    global _predictor
    if _predictor is None:
        _predictor = LSTMPredictor()
        _predictor.load()
    return _predictor