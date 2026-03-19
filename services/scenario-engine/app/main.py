from fastapi import FastAPI
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api import ingest, basins, scenarios
from app.core.lstm_predictor import get_predictor

load_dotenv()

# ── Lifespan PRIMERO, antes de crear la app ───────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    predictor = get_predictor()
    if predictor.is_ready:
        print("[startup] LSTM listo")
    else:
        print("[startup] LSTM no disponible — usando Manning como fallback")
    yield

# ── Una sola instancia con todo configurado ───────────────────────────────────
app = FastAPI(title="Fluvi Scenario Engine", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router)
app.include_router(basins.router)
app.include_router(scenarios.router)
