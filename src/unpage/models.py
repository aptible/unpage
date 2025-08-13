from datetime import datetime

from pydantic import AwareDatetime, BaseModel


class LogLine(BaseModel):
    time: datetime
    log: str


class Observation(BaseModel):
    node_id: str
    observation_type: str
    data: dict[AwareDatetime, float]
