from typing import Any

from pydantic import BaseModel


class RootlyIncident(BaseModel):
    """Represents a Rootly incident."""

    id: str
    attributes: dict[str, Any]
    type: str = "incidents"


class RootlyIncidentPayload(BaseModel):
    """Represents a Rootly incident payload for webhooks."""

    incident: RootlyIncident
