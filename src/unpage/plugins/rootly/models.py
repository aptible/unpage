from pydantic import BaseModel
from typing import Any, Dict
from collections.abc import AsyncGenerator
from pydantic import AwareDatetime


class RootlyIncident(BaseModel):
    """Represents a Rootly incident."""

    id: str
    attributes: Dict[str, Any]
    type: str = "incidents"


class RootlyIncidentPayload(BaseModel):
    """Represents a Rootly incident payload for webhooks."""

    incident: RootlyIncident