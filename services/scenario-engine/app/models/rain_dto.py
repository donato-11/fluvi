from pydantic import BaseModel
from datetime import datetime


class RainDTO(BaseModel):
    rainfall_mm: float        # Intensidad de lluvia (mm)
    duration_min: int         # Duración del evento
    basin_area_km2: float     # Área de la cuenca
    timestamp: datetime       # Tiempo del evento
