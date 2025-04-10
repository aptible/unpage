from datetime import datetime

import msgspec
from pydantic import AwareDatetime, BaseModel


class LogAnomaly(BaseModel):
    pattern: str
    peak_increase: float
    peak_time: AwareDatetime
    counts_sparkline: str


class LogLine(msgspec.Struct):
    time: datetime
    log: str


class Observation(BaseModel):
    node_id: str
    observation_type: str
    data: dict[AwareDatetime, float]
