from app.models.rain_dto import RainDTO


def calculate_level(data: RainDTO) -> float:
    """
    Simple hydrological model (placeholder).
    Later this will be replaced by:
    - terrain slope
    - flow accumulation
    - ML model (LSTM)
    """

    runoff_coefficient = 0.6  # simplificado
    volume = (
        data.rainfall_mm
        * data.basin_area_km2
        * runoff_coefficient
    )

    water_level = volume / 1000  # escala arbitraria para demo

    return round(water_level, 3)
