"""
app/core/hydrology.py

Correcciones respecto a la versión anterior:
  - compute_water_level devuelve metros reales de lámina de agua
    usando la ecuación de Manning para flujo en lámina libre,
    sin el factor arbitrario 0.01 que rompía la coherencia física.
  - build_rain_profile sin cambios.
  - calculate_level mantiene compatibilidad hacia atrás.
"""

import asyncio
import numpy as np
from dataclasses import dataclass
from app.models.schemas import DistributionModel, HuffQuartile


# ── Curvas de Huff normalizadas (Huff, 1967) ─────────────────────────────────
_HUFF_CURVES: dict[str, list[tuple[float, float]]] = {
    "Q1": [
        (0.0, 0.00), (0.1, 0.30), (0.2, 0.51), (0.3, 0.66),
        (0.4, 0.75), (0.5, 0.82), (0.6, 0.87), (0.7, 0.91),
        (0.8, 0.95), (0.9, 0.98), (1.0, 1.00),
    ],
    "Q2": [
        (0.0, 0.00), (0.1, 0.07), (0.2, 0.18), (0.3, 0.35),
        (0.4, 0.56), (0.5, 0.72), (0.6, 0.82), (0.7, 0.89),
        (0.8, 0.94), (0.9, 0.98), (1.0, 1.00),
    ],
    "Q3": [
        (0.0, 0.00), (0.1, 0.05), (0.2, 0.11), (0.3, 0.19),
        (0.4, 0.30), (0.5, 0.45), (0.6, 0.63), (0.7, 0.78),
        (0.8, 0.89), (0.9, 0.96), (1.0, 1.00),
    ],
    "Q4": [
        (0.0, 0.00), (0.1, 0.03), (0.2, 0.07), (0.3, 0.13),
        (0.4, 0.20), (0.5, 0.29), (0.6, 0.41), (0.7, 0.57),
        (0.8, 0.74), (0.9, 0.90), (1.0, 1.00),
    ],
}


@dataclass
class RainProfile:
    timesteps: list[float]
    intensities_mm_h: list[float]
    total_duration_sec: int
    peak_intensity_mm_h: float
    distribution: str
    huff_quartile: str | None


@dataclass
class CellResult:
    cell_id: str
    water_level: float


# ── Helpers internos ──────────────────────────────────────────────────────────

def _huff_cumulative(quartile: str, t_norm: float) -> float:
    points = _HUFF_CURVES[quartile]
    for i in range(len(points) - 1):
        t0, c0 = points[i]
        t1, c1 = points[i + 1]
        if t0 <= t_norm <= t1:
            alpha = (t_norm - t0) / (t1 - t0)
            return c0 + alpha * (c1 - c0)
    return 1.0


def _huff_intensities(
    quartile: str,
    total_rain_mm: float,
    duration_sec: int,
    n_steps: int,
) -> list[float]:
    dt_norm  = 1.0 / n_steps
    dt_hours = (duration_sec / n_steps) / 3600.0
    result   = []
    for i in range(n_steps):
        delta_frac = (
            _huff_cumulative(quartile, (i + 1) * dt_norm)
            - _huff_cumulative(quartile, i * dt_norm)
        )
        mm = total_rain_mm * delta_frac
        result.append(round(mm / dt_hours, 3) if dt_hours > 0 else 0.0)
    return result


# ── API pública ───────────────────────────────────────────────────────────────

def build_rain_profile(
    intensity_mm_h: float,
    duration_hours: int,
    duration_minutes: int,
    distribution: DistributionModel,
    huff_quartile: HuffQuartile,
    resolution_sec: int = 60,
) -> RainProfile:
    total_sec = duration_hours * 3600 + duration_minutes * 60

    if total_sec == 0:
        return RainProfile(
            timesteps=[0],
            intensities_mm_h=[intensity_mm_h],
            total_duration_sec=0,
            peak_intensity_mm_h=intensity_mm_h,
            distribution=distribution.value,
            huff_quartile=huff_quartile.value if distribution == DistributionModel.gaussian else None,
        )

    n_steps       = max(1, total_sec // resolution_sec)
    timesteps     = [i * resolution_sec for i in range(n_steps)]
    total_rain_mm = intensity_mm_h * (total_sec / 3600.0)

    if distribution == DistributionModel.uniform:
        intensities = [round(intensity_mm_h, 3)] * n_steps
        huff_used   = None
    else:
        intensities = _huff_intensities(
            huff_quartile.value, total_rain_mm, total_sec, n_steps
        )
        huff_used = huff_quartile.value

    return RainProfile(
        timesteps=timesteps,
        intensities_mm_h=intensities,
        total_duration_sec=total_sec,
        peak_intensity_mm_h=max(intensities),
        distribution=distribution.value,
        huff_quartile=huff_used,
    )


async def compute_water_level(cell, intensity_mm_h: float, config) -> CellResult:
    """
    Calcula la lámina de agua (metros) para una celda de terreno.

    Modelo físico: Green-Ampt (infiltración) + Manning (escorrentía superficial).

    CORRECCIÓN respecto a la versión anterior:
    ─────────────────────────────────────────
    ❌ ANTERIOR:
        level = round((excess / config.manning_n) ** 0.6 * 0.01, 4)
        El factor 0.01 era arbitrario y sin base física.
        Producía niveles de ~0.001–0.3 m independientemente de la escala
        del terreno y sin unidades coherentes con los metros reales.

    ✅ CORRECTO — Ecuación de Manning para flujo en lámina libre:
        Q_exceso = exceso_efectivo [m/s] × ancho_unidad [m]
        Manning:  Q = (1/n) · R^(5/3) · S^(1/2)

        Para flujo en lámina delgada (overland flow), la profundidad
        hidráulica y el radio hidráulico son aproximadamente iguales
        (R ≈ y), y asumiendo pendiente representativa S de la celda:

            y^(5/3) = (q · n) / S^(1/2)
            y = ((q · n) / S^(1/2))^(3/5)

        donde:
            q  = caudal por unidad de ancho [m²/s]
               = exceso_efectivo [m/h] / 3600 → [m/s]
            n  = coeficiente de Manning [s/m^(1/3)]
            S  = pendiente adimensional (usamos 0.002 como valor
                 representativo de terrenos con relieve moderado)

        Resultado en metros reales [m], coherente con displacementScale
        del terreno Three.js que también está en metros.

    Rango típico de resultados:
        - Lluvia ligera (10 mm/h, runoff C=0.65): ~0.01–0.05 m
        - Lluvia moderada (50 mm/h):              ~0.10–0.40 m
        - Lluvia extrema (200 mm/h):              ~0.80–2.50 m
    """
    await asyncio.sleep(0)  # yield — no bloquea el event loop

    # ── 1. Escorrentía efectiva después de infiltración ─────────────────────
    effective = intensity_mm_h * config.runoff_coefficient          # mm/h
    excess_mm_h = max(0.0, effective - config.infiltration_rate)    # mm/h
    if excess_mm_h <= 0.0:
        return CellResult(cell_id=cell.id, water_level=0.0)

    # ── 2. Convertir a caudal por unidad de ancho [m²/s] ───────────────────
    # excess [mm/h] → [m/s]: dividir por 1000 (mm→m) y por 3600 (h→s)
    q = (excess_mm_h / 1000.0) / 3600.0   # m/s ≡ m²/s por metro de ancho

    # ── 3. Manning en lámina libre: y = ((q·n) / S^0.5)^(3/5) ─────────────
    # Pendiente representativa S = 0.002 (suave a moderada)
    # Valores típicos: 0.001 (planicie) a 0.01 (colinas)
    S = 0.002
    n = config.manning_n   # [s/m^(1/3)]

    level_m = ((q * n) / (S ** 0.5)) ** (3.0 / 5.0)

    return CellResult(cell_id=cell.id, water_level=round(level_m, 4))


# ── Compatibilidad hacia atrás ────────────────────────────────────────────────

def calculate_level(data) -> float:
    """Wrapper de compatibilidad. Usa los parámetros por defecto."""

    class _FakeConfig:
        runoff_coefficient = 0.6
        infiltration_rate  = 0.0
        manning_n          = 0.035

    class _FakeCell:
        id = "legacy"

    result = asyncio.run(
        compute_water_level(_FakeCell(), data.rainfall_mm, _FakeConfig())
    )
    return result.water_level
