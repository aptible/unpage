from typing import Any

from pydantic import AwareDatetime, BaseModel


class PagerDutyService(BaseModel):
    id: str
    type: str
    summary: str
    html_url: str


class PagerDutyAssignee(BaseModel):
    id: str
    type: str
    summary: str
    html_url: str


class PagerDutyAssignment(BaseModel):
    at: AwareDatetime
    assignee: PagerDutyAssignee


class PagerDutyAlertCounts(BaseModel):
    all: int
    triggered: int
    resolved: int


class PagerDutyIncidentType(BaseModel):
    name: str


class PagerDutyEscalationPolicy(BaseModel):
    id: str
    type: str
    summary: str
    html_url: str


class PagerDutyTeam(BaseModel):
    id: str
    html_url: str


class PagerDutyIncident(BaseModel):
    incident_number: int
    title: str
    description: str
    created_at: AwareDatetime
    updated_at: AwareDatetime
    status: str
    incident_key: str | None = None
    service: PagerDutyService
    assignments: list[PagerDutyAssignment] | None = None
    assigned_via: str | None = None
    last_status_changed_at: AwareDatetime | None = None
    resolved_at: AwareDatetime | None = None
    alert_counts: PagerDutyAlertCounts
    is_mergeable: bool
    incident_type: PagerDutyIncidentType
    escalation_policy: PagerDutyEscalationPolicy
    teams: list[PagerDutyTeam] | None = None
    impacted_services: list[PagerDutyService] | None = None
    pending_actions: list | None = None
    acknowledgements: list | None = None
    basic_alert_grouping: Any | None = None
    alert_grouping: Any | None = None
    last_status_change_by: Any
    incident_responders: list | None = None
    responder_requests: list | None = None
    subscriber_requests: list | None = None
    urgency: str
    id: str
    type: str
    summary: str
    html_url: str


class PagerDutyIncidentPayload(BaseModel):
    incident: PagerDutyIncident
