from fastapi import FastAPI
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

from app.api import ingest, basins, scenarios

app = FastAPI(title="Fluvi Scenario Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

load_dotenv()


app.include_router(ingest.router)
app.include_router(basins.router)
app.include_router(scenarios.router)
