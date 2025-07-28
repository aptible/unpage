from typing import Any

from pydantic import AwareDatetime, BaseModel


class DatadogLogEventAttributes(BaseModel):
    timestamp: AwareDatetime
    host: str
    service: str
    status: str
    tags: list[str]
    attributes: dict[str, Any]


class DatadogLogEvent(BaseModel):
    """Datadog log event"""

    """ID of the Log"""
    id: str
    """Type of event (always log)"""
    type: str = "log"
    """All other log attributes"""
    attributes: DatadogLogEventAttributes


class DatadogLogSearchResult(BaseModel):
    """Result of a DataDog log search."""

    """True when the search results were truncated due to the response size limit or single search time limit"""
    truncated: bool = False
    """The log events that were found"""
    results: list[DatadogLogEvent]
