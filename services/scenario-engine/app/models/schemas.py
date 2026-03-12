from pydantic import BaseModel, Field
from enum import Enum


class DistributionModel(str, Enum):
    gaussian = "gaussian"
    uniform = "uniform"


class HuffQuartile(str, Enum):
    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"


class RainfallConfig(BaseModel):
    intensity_mm_h: float = Field(..., ge=0, le=200)
    duration_hours: int = Field(..., ge=0, le=72)
    duration_minutes: int = Field(..., ge=0, le=59)
    distribution_model: DistributionModel = DistributionModel.gaussian
    huff_quartile: HuffQuartile = HuffQuartile.Q2


class HydraulicsConfig(BaseModel):
    infiltration_rate: float = Field(default=12.5)
    runoff_coefficient: float = Field(default=0.65, ge=0, le=1)
    manning_n: float = Field(default=0.035)


class StartSimulationRequest(BaseModel):
    region_id: str
    speed: float = 1.0
    rainfall: RainfallConfig
    hydraulics: HydraulicsConfig


class SimulationStatus(str, Enum):
    idle = "idle"
    running = "running"
    paused = "paused"
    stopped = "stopped"


class SimulationResponse(BaseModel):
    simulation_id: str
    status: SimulationStatus
    region_id: str