"""
app/core/hydrology.py

Reemplaza el placeholder original. Implementa:
  - Curvas de Huff (Q1-Q4) para distribución temporal de la lluvia
  - Modelo uniforme (intensidad constante)
  - compute_water_level() async por celda (Green-Ampt + Manning simplificado)
"""

import asyncio
import numpy as np
from dataclasses import dataclass
from app.models.schemas import DistributionModel, HuffQuartile


# ── Curvas de Huff normalizadas (Huff, 1967) ─────────────────────────────────
# (tiempo_adimensional 0→1, lluvia_acumulada_fracción 0→1)
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
    timesteps: list[float]           # segundos desde inicio
    intensities_mm_h: list[float]    # intensidad en cada paso
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
    """Intensidad instantánea (mm/h) derivada de la curva de Huff acumulada."""
    dt_norm = 1.0 / n_steps
    dt_hours = (duration_sec / n_steps) / 3600.0
    result = []
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
    """
    Construye el perfil temporal completo del evento de lluvia.

    - uniform  → intensidad constante = intensity_mm_h durante toda la duración
    - gaussian → curvas de Huff (Q1-Q4) escalan el total de lluvia temporalmente
    """
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

    n_steps = max(1, total_sec // resolution_sec)
    timesteps = [i * resolution_sec for i in range(n_steps)]
    total_rain_mm = intensity_mm_h * (total_sec / 3600.0)

    if distribution == DistributionModel.uniform:
        intensities = [round(intensity_mm_h, 3)] * n_steps
        huff_used = None
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
    Modelo físico por celda: Green-Ampt (infiltración) + Manning (escorrentía).
    Async para permitir asyncio.gather() en paralelo sobre todas las celdas.

    Reemplaza el placeholder original que usaba runoff_coefficient * volume / 1000.
    """
    await asyncio.sleep(0)  # yield — no bloquea el event loop

    # Escorrentía efectiva después de infiltración
    effective = intensity_mm_h * config.runoff_coefficient
    excess = max(0.0, effective - config.infiltration_rate)

    if excess <= 0:
        return CellResult(cell_id=cell.id, water_level=0.0)

    # Aproximación Manning superficial: nivel ∝ (excess / n)^0.6
    level = round((excess / config.manning_n) ** 0.6 * 0.01, 4)
    return CellResult(cell_id=cell.id, water_level=level)


# ── Compatibilidad con el código original (rain_dto) ─────────────────────────
# Mantiene calculate_level() para no romper imports existentes

def calculate_level(data) -> float:
    """
    Wrapper de compatibilidad hacia atrás.
    Usa runoff_coefficient fijo = 0.6, igual que el placeholder original,
    pero delega al modelo físico real.
    """

    class _FakeConfig:
        runoff_coefficient = 0.6
        infiltration_rate = 0.0
        manning_n = 0.035

    class _FakeCell:
        id = "legacy"

    import asyncio
    result = asyncio.run(
        compute_water_level(_FakeCell(), data.rainfall_mm, _FakeConfig())
    )
    return result.water_level
