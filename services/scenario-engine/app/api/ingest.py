from fastapi import APIRouter

from app.models.rain_dto import RainDTO
from app.core.hydrology import calculate_level

router = APIRouter(
    prefix="/ingest",
    tags=["ingestion"]
)


@router.post("/rainfall")
def ingest_rainfall(data: RainDTO):
    level = calculate_level(data)

    return {
        "water_level": level,
        "timestamp": data.timestamp
    }



