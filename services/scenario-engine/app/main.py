from fastapi import FastAPI
from app.api import ingest, basins

app = FastAPI(title="Fluvi Scenario Engine")

app.include_router(ingest.router)
app.include_router(basins.router)
