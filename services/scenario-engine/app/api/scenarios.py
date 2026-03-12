"""
app/api/scenarios.py
Endpoints REST: start, pause, resume, reset, stop, results.
"""
import asyncio
import httpx
from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.models.schemas import (
    StartSimulationRequest, SimulationResponse, SimulationStatus,
)
from app.core.state import SimulationState, TerrainCell
from app.core.hydrology import build_rain_profile, compute_water_level

router = APIRouter(prefix="/scenarios", tags=["scenarios"])

GATEWAY_URL = "http://localhost:3001"


def _mock_terrain_cells(region_id: str) -> list[TerrainCell]:
    """Celdas de prueba. Reemplazar con consulta PostGIS."""
    return [
        TerrainCell(id=f"{region_id}-cell-{i}", elevation=float(i % 10))
        for i in range(20)
    ]


async def _notify_gateway(sim_id: str, intensity: float, sim) -> None:
    """Envía el tick actual al API Gateway vía HTTP POST."""
    print(f"[notify] step={sim.current_step} level={sim.current_water_level}")  # ← agregar

    payload = {
        "simulationId": sim_id,
        "waterLevel": sim.current_water_level,
        "intensity": intensity,
        "accumulatedRain": round(sim.accumulated_rain, 3),
        "step": sim.current_step,
        "timestamp": int(asyncio.get_event_loop().time() * 1000),
    }
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{GATEWAY_URL}/streaming/update",
                json=payload,
                timeout=2.0,
            )
            print(f"[notify] gateway responded {r.status_code}")  # ← agregar

    except Exception as e:
        print(f"[notify] ERROR: {e}")  # ← cambiar pass por esto

async def _run_simulation_loop(sim_id: str) -> None:
    """
    Background task: avanza ticks, calcula nivel por celda en paralelo
    y notifica al API Gateway → Socket.IO → frontend.
    """
    while True:
        intensity = SimulationState.advance_step(sim_id)

        if intensity is None:
            break

        sim = SimulationState.get(sim_id)
        if not sim:
            break

        # Cálculo paralelo por celda (Green-Ampt + Manning)
        results = await asyncio.gather(*[
            compute_water_level(cell, intensity, sim.config)
            for cell in sim.terrain_cells
        ])

        if results:
            sim.current_water_level = round(
                sum(r.water_level for r in results) / len(results), 4
            )

        # Notificar al gateway → Socket.IO → frontend
        await _notify_gateway(sim_id, intensity, sim)

        await asyncio.sleep(1.0 / max(sim.speed, 0.1))


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("", response_model=SimulationResponse, status_code=201)
async def start_simulation(body: StartSimulationRequest, background_tasks: BackgroundTasks):
    rain_profile = build_rain_profile(
        intensity_mm_h=body.rainfall.intensity_mm_h,
        duration_hours=body.rainfall.duration_hours,
        duration_minutes=body.rainfall.duration_minutes,
        distribution=body.rainfall.distribution_model,
        huff_quartile=body.rainfall.huff_quartile,
    )
    sim = SimulationState.create(
        region_id=body.region_id,
        speed=body.speed,
        rainfall=body.rainfall,
        hydraulics=body.hydraulics,
        rain_profile=rain_profile,
        terrain_cells=_mock_terrain_cells(body.region_id),
    )
    background_tasks.add_task(_run_simulation_loop, sim.simulation_id)

    return SimulationResponse(
        simulation_id=sim.simulation_id,
        status=sim.status,
        region_id=sim.region_id,
    )


@router.get("/{sim_id}/results")
async def get_results(sim_id: str):
    sim = SimulationState.get(sim_id)
    if not sim:
        raise HTTPException(404, "Simulation not found")

    profile = sim.rain_profile
    current_intensity = (
        profile.intensities_mm_h[sim.current_step - 1]
        if sim.current_step > 0 else 0.0
    )

    return {
        "simulation_id": sim_id,
        "status": sim.status,
        "current_step": sim.current_step,
        "total_steps": len(profile.intensities_mm_h),
        "progress_pct": round(sim.current_step / max(len(profile.intensities_mm_h), 1) * 100, 1),
        "accumulated_rain_mm": round(sim.accumulated_rain, 3),
        "current_intensity_mm_h": current_intensity,
        "current_water_level_m": sim.current_water_level,
        "cells": [
            {"cell_id": cell.id, "elevation": cell.elevation}
            for cell in sim.terrain_cells
        ],
    }


@router.get("/{sim_id}", response_model=SimulationResponse)
async def get_simulation(sim_id: str):
    sim = SimulationState.get(sim_id)
    if not sim:
        raise HTTPException(404, "Simulation not found")
    return SimulationResponse(simulation_id=sim_id, status=sim.status, region_id=sim.region_id)


@router.post("/{sim_id}/pause", response_model=SimulationResponse)
async def pause_simulation(sim_id: str):
    sim = SimulationState.get(sim_id)
    if not sim:
        raise HTTPException(404, "Simulation not found")
    new_status = SimulationState.pause(sim_id)
    if new_status is None:
        raise HTTPException(409, f"Cannot pause: current status is '{sim.status}'")
    return SimulationResponse(simulation_id=sim_id, status=new_status, region_id=sim.region_id)


@router.post("/{sim_id}/resume", response_model=SimulationResponse)
async def resume_simulation(sim_id: str):
    sim = SimulationState.get(sim_id)
    if not sim:
        raise HTTPException(404, "Simulation not found")
    new_status = SimulationState.resume(sim_id)
    if new_status is None:
        raise HTTPException(409, f"Cannot resume: current status is '{sim.status}'")
    asyncio.create_task(_run_simulation_loop(sim_id))
    return SimulationResponse(simulation_id=sim_id, status=new_status, region_id=sim.region_id)


@router.post("/{sim_id}/reset", response_model=SimulationResponse)
async def reset_simulation(sim_id: str):
    sim = SimulationState.get(sim_id)
    if not sim:
        raise HTTPException(404, "Simulation not found")
    new_status = SimulationState.reset(sim_id)
    return SimulationResponse(simulation_id=sim_id, status=new_status, region_id=sim.region_id)


@router.delete("/{sim_id}", status_code=204)
async def stop_simulation(sim_id: str):
    SimulationState.stop(sim_id)