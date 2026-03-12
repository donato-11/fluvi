"""
app/api/ingest.py
Recibe lecturas del climate-ingestor. Usa el perfil Huff/uniform pre-calculado.
"""

import asyncio
import httpx
import os

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.hydrology import compute_water_level
from app.core.state import SimulationState
from app.models.schemas import SimulationStatus

router = APIRouter(tags=["ingest"])

GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://localhost:3000")


class RainfallReading(BaseModel):
    simulation_id: str
    node_id: str
    timestamp: int
    source: str           # "simulator" | "sensor" — agnóstico
    intensity_mm_h: float


@router.post("/ingest/rainfall")
async def ingest_rainfall(reading: RainfallReading):
    sim = SimulationState.get(reading.simulation_id)

    if not sim:
        return {"status": "ignored", "reason": "simulation not found"}

    if sim.status == SimulationStatus.paused:
        return {"status": "ignored", "reason": "simulation paused"}

    if sim.status == SimulationStatus.idle:
        return {"status": "ignored", "reason": "simulation idle"}

    # Avanzar en el perfil pre-calculado (Huff o uniform)
    # La intensidad del simulador actúa como TRIGGER, no como valor directo
    profile_intensity = SimulationState.advance_step(reading.simulation_id)

    if profile_intensity is None:
        return {"status": "ignored", "reason": "simulation ended or paused"}

    # Calcular nivel de agua en paralelo por celda (M3 concurrencia)
    tasks = [
        compute_water_level(cell, profile_intensity, sim.config)
        for cell in sim.terrain_cells
    ]
    results = await asyncio.gather(*tasks)

    avg_level = sum(r.water_level for r in results) / len(results)
    sim.current_water_level = avg_level

    await _notify_gateway(
        simulation_id=reading.simulation_id,
        water_level=avg_level,
        intensity=profile_intensity,
        accumulated_rain=sim.accumulated_rain,
        step=sim.current_step,
        timestamp=reading.timestamp,
    )

    return {
        "status": "ok",
        "water_level": avg_level,
        "profile_intensity": profile_intensity,
        "step": sim.current_step,
    }


async def _notify_gateway(
    simulation_id: str,
    water_level: float,
    intensity: float,
    accumulated_rain: float,
    step: int,
    timestamp: int,
):
    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                f"{GATEWAY_URL}/streaming/update",
                json={
                    "simulationId": simulation_id,
                    "waterLevel": water_level,
                    "intensity": intensity,
                    "accumulatedRain": accumulated_rain,
                    "step": step,
                    "timestamp": timestamp,
                },
                timeout=3.0,
            )
        except httpx.RequestError as e:
            print(f"[ingest] Warning: gateway unreachable: {e}")


