"""
app/core/state.py
Gestión thread-safe del ciclo de vida de simulaciones activas.
"""

import uuid
import threading
from dataclasses import dataclass
from typing import Optional

from app.models.schemas import SimulationStatus, RainfallConfig, HydraulicsConfig
from app.core.hydrology import RainProfile


@dataclass
class TerrainCell:
    id: str
    elevation: float


@dataclass
class SimConfig:
    infiltration_rate: float = 12.5
    runoff_coefficient: float = 0.65
    manning_n: float = 0.035


@dataclass
class ActiveSimulation:
    simulation_id: str
    region_id: str
    speed: float
    rainfall: RainfallConfig
    hydraulics: HydraulicsConfig
    rain_profile: RainProfile
    config: SimConfig
    terrain_cells: list[TerrainCell]
    status: SimulationStatus = SimulationStatus.running
    accumulated_rain: float = 0.0
    current_step: int = 0
    current_water_level: float = 0.0


_store: dict[str, ActiveSimulation] = {}
_lock = threading.Lock()


class SimulationState:

    @staticmethod
    def get(sim_id: str) -> Optional[ActiveSimulation]:
        return _store.get(sim_id)

    @staticmethod
    def create(
        region_id: str,
        speed: float,
        rainfall: RainfallConfig,
        hydraulics: HydraulicsConfig,
        rain_profile: RainProfile,
        terrain_cells: list[TerrainCell],
    ) -> ActiveSimulation:
        sim_id = str(uuid.uuid4())
        config = SimConfig(
            infiltration_rate=hydraulics.infiltration_rate,
            runoff_coefficient=hydraulics.runoff_coefficient,
            manning_n=hydraulics.manning_n,
        )
        sim = ActiveSimulation(
            simulation_id=sim_id,
            region_id=region_id,
            speed=speed,
            rainfall=rainfall,
            hydraulics=hydraulics,
            rain_profile=rain_profile,
            config=config,
            terrain_cells=terrain_cells,
            status=SimulationStatus.running,
        )
        with _lock:
            _store[sim_id] = sim
        return sim

    @staticmethod
    def pause(sim_id: str) -> Optional[SimulationStatus]:
        sim = _store.get(sim_id)
        if sim and sim.status == SimulationStatus.running:
            with _lock:
                sim.status = SimulationStatus.paused
            return sim.status
        return None

    @staticmethod
    def resume(sim_id: str) -> Optional[SimulationStatus]:
        sim = _store.get(sim_id)
        if sim and sim.status == SimulationStatus.paused:
            with _lock:
                sim.status = SimulationStatus.running
            return sim.status
        return None

    @staticmethod
    def reset(sim_id: str) -> Optional[SimulationStatus]:
        """Reinicia contadores sin eliminar la simulación."""
        sim = _store.get(sim_id)
        if sim:
            with _lock:
                sim.accumulated_rain = 0.0
                sim.current_step = 0
                sim.current_water_level = 0.0
                sim.status = SimulationStatus.idle
            return sim.status
        return None

    @staticmethod
    def stop(sim_id: str):
        with _lock:
            _store.pop(sim_id, None)

    @staticmethod
    def advance_step(sim_id: str) -> Optional[float]:
        """
        Avanza un paso en el perfil de lluvia.
        Devuelve la intensidad del paso actual, o None si está pausada/terminó.
        """
        sim = _store.get(sim_id)
        if not sim or sim.status != SimulationStatus.running:
            return None

        profile = sim.rain_profile
        if sim.current_step >= len(profile.intensities_mm_h):
            with _lock:
                sim.status = SimulationStatus.idle
            return None

        intensity = profile.intensities_mm_h[sim.current_step]
        with _lock:
            sim.current_step += 1
            sim.accumulated_rain += intensity * (60 / 3600)  # paso 60s → mm
        return intensity