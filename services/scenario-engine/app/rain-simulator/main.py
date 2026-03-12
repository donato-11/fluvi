"""
rain-simulator/main.py
Nodo generador de lluvia — Distribución Gamma
Corre independiente (laptop, VM, Raspberry Pi, etc.)
"""

import asyncio
import json
import time
import uuid
import numpy as np
import websockets
from dataclasses import dataclass, asdict
from typing import Optional

# ── Config ────────────────────────────────────────────────────────────────────
INGESTOR_WS_URL = "ws://localhost:3001/rainfall"   # climate-ingestor WS
NODE_ID = f"rain-node-{uuid.uuid4().hex[:6]}"
EMIT_INTERVAL_SEC = 2.0                             # cada 2s emite una lectura
HEARTBEAT_INTERVAL_SEC = 5.0


# ── Distribución Gamma para lluvia ────────────────────────────────────────────
# shape (k) y scale (θ) típicos para tormentas moderadas
# E[X] = k*θ  |  Var[X] = k*θ²
@dataclass
class GammaRainfallConfig:
    shape: float = 2.0      # k  — controla la forma (pico de la tormenta)
    scale: float = 5.0      # θ  — controla la intensidad base (mm/h)
    noise_std: float = 0.5  # ruido gaussiano para simular sensor real


def sample_rainfall(cfg: GammaRainfallConfig) -> float:
    """Genera una lectura de lluvia usando Distribución Gamma + ruido sensor."""
    base = np.random.gamma(shape=cfg.shape, scale=cfg.scale)
    noise = np.random.normal(0, cfg.noise_std)
    return round(max(0.0, base + noise), 2)


# ── Payloads ──────────────────────────────────────────────────────────────────
def make_rainfall_payload(
    intensity: float,
    simulation_id: str,
    cfg: GammaRainfallConfig,
) -> dict:
    return {
        "event": "rainfall:data",
        "nodeId": NODE_ID,
        "simulationId": simulation_id,
        "timestamp": int(time.time() * 1000),
        "source": "simulator",          # ← agnóstico: "sensor" | "simulator"
        "data": {
            "intensity_mm_h": intensity,
            "distribution": "gamma",
            "params": {"shape": cfg.shape, "scale": cfg.scale},
        },
    }


def make_heartbeat_payload(simulation_id: str) -> dict:
    return {
        "event": "heartbeat",
        "nodeId": NODE_ID,
        "simulationId": simulation_id,
        "timestamp": int(time.time() * 1000),
    }


# ── Tasks async ───────────────────────────────────────────────────────────────
async def emit_rainfall(
    ws: websockets.WebSocketClientProtocol,
    simulation_id: str,
    cfg: GammaRainfallConfig,
):
    while True:
        intensity = sample_rainfall(cfg)
        payload = make_rainfall_payload(intensity, simulation_id, cfg)
        await ws.send(json.dumps(payload))
        print(f"[{NODE_ID}] ↑ rainfall {intensity} mm/h")
        await asyncio.sleep(EMIT_INTERVAL_SEC)


async def emit_heartbeat(
    ws: websockets.WebSocketClientProtocol,
    simulation_id: str,
):
    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL_SEC)
        payload = make_heartbeat_payload(simulation_id)
        await ws.send(json.dumps(payload))
        print(f"[{NODE_ID}] ♥ heartbeat")


async def run(simulation_id: str, cfg: Optional[GammaRainfallConfig] = None):
    cfg = cfg or GammaRainfallConfig()

    print(f"[{NODE_ID}] Conectando a {INGESTOR_WS_URL} ...")

    async with websockets.connect(INGESTOR_WS_URL) as ws:
        print(f"[{NODE_ID}] Conectado. Iniciando simulación {simulation_id}")

        # Registrar nodo
        await ws.send(json.dumps({
            "event": "node:register",
            "nodeId": NODE_ID,
            "simulationId": simulation_id,
        }))

        # Correr rainfall + heartbeat en paralelo
        await asyncio.gather(
            emit_rainfall(ws, simulation_id, cfg),
            emit_heartbeat(ws, simulation_id),
        )


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fluvi Rain Simulator")
    parser.add_argument("--sim-id", required=True, help="ID de la simulación activa")
    parser.add_argument("--shape", type=float, default=2.0)
    parser.add_argument("--scale", type=float, default=5.0)
    args = parser.parse_args()

    cfg = GammaRainfallConfig(shape=args.shape, scale=args.scale)
    asyncio.run(run(args.sim_id, cfg))