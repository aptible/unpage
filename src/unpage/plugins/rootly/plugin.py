import os
from collections.abc import AsyncGenerator
from typing import Any

import questionary
import rich
from pydantic import AwareDatetime, BaseModel

from unpage.config import PluginSettings
from unpage.knowledge import Graph
from unpage.plugins.base import Plugin
from unpage.plugins.mixins import KnowledgeGraphMixin, McpServerMixin, tool
from unpage.plugins.rootly.client import RootlyClient
from unpage.plugins.rootly.models import RootlyIncident, RootlyIncidentPayload
from unpage.utils import classproperty


class RootlyPluginSettings(BaseModel):
    api_key: str = ""


class RootlyPlugin(Plugin, KnowledgeGraphMixin, McpServerMixin):
    """A plugin for Rootly."""

    _client: RootlyClient

    def __init__(
        self,
        *args: Any,
        api_key: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._api_key = api_key or os.getenv("ROOTLY_API_KEY", "")
        self._client = RootlyClient(api_key=self._api_key)

    @classproperty
    def default_plugin_settings(cls) -> PluginSettings:
        return RootlyPluginSettings(
            api_key=os.environ.get("ROOTLY_API_KEY", ""),
        ).model_dump()

    async def interactive_configure(self) -> PluginSettings:
        """Interactive wizard for configuring the settings of this plugin."""
        defaults = self.default_plugin_settings
        rich.print(
            "[bold]Rootly Plugin Configuration[/bold]: This plugin enables interaction with Rootly incidents. You'll need an API key from your Rootly organization settings."
        )
        rich.print("")
        return {
            "api_key": await questionary.password(
                "API Key",
                default=self._api_key or defaults.get("api_key", ""),
                instruction="Generate a token from Organization Settings > API Keys in Rootly",
            ).unsafe_ask_async(),
        }

    async def validate_plugin_config(self) -> None:
        if not self._api_key:
            raise LookupError("plugins.rootly.settings.api_key (or $ROOTLY_API_KEY) must be set")
        # Test API connectivity
        await self._client.list_incidents({"page[size]": "1"})

    @tool()
    async def list_recent_incidents(self, limit: int = 10) -> list[dict[str, Any]]:
        """List recent Rootly incidents

        Args:
            limit (int): Maximum number of incidents to return (default: 10)

        Returns:
            list[dict]: List of recent incidents with their details
        """
        params = {
            "sort": "-created_at",
            "page[size]": str(min(limit, 100)),  # API limit
        }
        response = await self._client.list_incidents(params)
        return response.get("data", [])

    @tool()
    async def get_incident_details(self, incident_id: str) -> dict[str, Any]:
        """Get a Rootly incident by ID, including all incident details.

        Args:
            incident_id (str): The ID of the Rootly incident. Typically a
            UUID string. For example "01234567-89ab-cdef-0123-456789abcdef".

        Returns:
            dict: The incident JSON payload, including all incident details.
        """
        return await self._client.get_incident(incident_id)

    @tool()
    async def get_alert_details_for_incident(self, incident_id: str) -> list[dict[str, Any]]:
        """Get the details of the alert(s) for a Rootly incident.

        Args:
            incident_id (str): The ID of the Rootly incident. Typically a
            UUID string. For example "01234567-89ab-cdef-0123-456789abcdef".

        Returns:
            list[dict]: The list of alert details (incident events).
        """
        response = await self._client.get_incident_events(incident_id)
        return response.get("data", [])

    @tool()
    async def post_status_update(
        self, incident_id: str, message: str, visibility: str = "external"
    ) -> None:
        """Post a status update to a Rootly incident

        Args:
            incident_id (str): The Rootly ID of the incident
            message (str): The message to post
            visibility (str): Event visibility - "internal" or "external" (default: "external")
        """
        await self.add_incident_event(incident_id, f"Status Update: {message}", visibility)

    @tool()
    async def add_incident_event(
        self, incident_id: str, event_description: str, visibility: str = "internal"
    ) -> dict[str, Any]:
        """Add a timeline event to a Rootly incident for root cause analysis

        Args:
            incident_id (str): The Rootly ID of the incident
            event_description (str): Description of the event/activity
            visibility (str): Event visibility - "internal" or "external" (default: "internal")

        Returns:
            dict: The created event data

        Note: Creates structured timeline entries for proper incident tracking
        and root cause analysis. Events are timestamped automatically by Rootly.
        """
        event_data = {
            "data": {
                "type": "incident_events",
                "attributes": {
                    "event": event_description,
                    "kind": "event",
                    "source": "api",
                    "visibility": visibility,
                },
            }
        }

        return await self._client.create_incident_event_new(incident_id, event_data)

    @tool()
    async def log_investigation_finding(
        self,
        incident_id: str,
        finding: str,
        source: str | None = None,
        visibility: str = "internal",
    ) -> dict[str, Any]:
        """Log an investigation finding for root cause analysis

        Args:
            incident_id (str): The Rootly ID of the incident
            finding (str): The investigation finding or discovery
            source (str, optional): Source of the finding (e.g., 'logs', 'metrics', 'database')
            visibility (str): Event visibility - "internal" or "external" (default: "internal")

        Returns:
            dict: The created event data
        """
        event_description = f"Investigation Finding: {finding}"
        if source:
            event_description += f" (Source: {source})"

        return await self.add_incident_event(incident_id, event_description, visibility)

    @tool()
    async def log_action_taken(
        self,
        incident_id: str,
        action: str,
        outcome: str | None = None,
        visibility: str = "internal",
    ) -> dict[str, Any]:
        """Log an action taken during incident response

        Args:
            incident_id (str): The Rootly ID of the incident
            action (str): The action that was taken
            outcome (str, optional): The result or outcome of the action
            visibility (str): Event visibility - "internal" or "external" (default: "internal")

        Returns:
            dict: The created event data
        """
        event_description = f"Action Taken: {action}"
        if outcome:
            event_description += f" → Result: {outcome}"

        return await self.add_incident_event(incident_id, event_description, visibility)

    @tool()
    async def log_escalation(
        self,
        incident_id: str,
        escalated_to: str,
        reason: str | None = None,
        visibility: str = "internal",
    ) -> dict[str, Any]:
        """Log an incident escalation

        Args:
            incident_id (str): The Rootly ID of the incident
            escalated_to (str): Who or what team the incident was escalated to
            reason (str, optional): Reason for the escalation
            visibility (str): Event visibility - "internal" or "external" (default: "internal")

        Returns:
            dict: The created event data
        """
        event_description = f"Escalated to {escalated_to}"
        if reason:
            event_description += f" - Reason: {reason}"

        return await self.add_incident_event(incident_id, event_description, visibility)

    @tool()
    async def log_communication(
        self, incident_id: str, communication_type: str, details: str, visibility: str = "external"
    ) -> dict[str, Any]:
        """Log a communication event (e.g., customer notification, internal update)

        Args:
            incident_id (str): The Rootly ID of the incident
            communication_type (str): Type of communication (e.g., "Customer Notification", "Team Update")
            details (str): Details of the communication
            visibility (str): Event visibility - "external" for customer-facing, "internal" for team-only

        Returns:
            dict: The created event data
        """
        event_description = f"{communication_type}: {details}"

        return await self.add_incident_event(incident_id, event_description, visibility)

    @tool()
    async def get_incident_timeline(self, incident_id: str) -> list[dict[str, Any]]:
        """Get the complete timeline of events for an incident

        Args:
            incident_id (str): The Rootly ID of the incident

        Returns:
            list: List of all events/timeline entries for the incident
        """
        response = await self._client.get_incident_events(incident_id)
        return response.get("data", [])

    @tool()
    async def update_incident_event(
        self, event_id: str, event_description: str, visibility: str = "internal"
    ) -> dict[str, Any]:
        """Update an existing incident event

        Args:
            event_id (str): The ID of the event to update
            event_description (str): Updated description of the event
            visibility (str): Event visibility - "internal" or "external" (default: "internal")

        Returns:
            dict: The updated event data
        """
        update_data = {
            "data": {
                "type": "incident_events",
                "id": event_id,
                "attributes": {"event": event_description, "visibility": visibility},
            }
        }

        return await self._client.update_incident_event(event_id, update_data)

    @tool()
    async def delete_incident_event(self, event_id: str) -> dict[str, Any]:
        """Delete an incident event

        Args:
            event_id (str): The ID of the event to delete

        Returns:
            dict: Response from the deletion request
        """
        return await self._client.delete_incident_event(event_id)

    @tool()
    async def resolve_incident(
        self, incident_id: str, resolution_message: str | None = None
    ) -> None:
        """Resolve a Rootly incident

        Args:
            incident_id (str): The ID of the Rootly incident to resolve
            resolution_message (str, optional): A message to include with the resolution
        """
        update_data = {
            "data": {"type": "incidents", "id": incident_id, "attributes": {"status": "resolved"}}
        }

        # Add resolution message if provided
        if resolution_message:
            update_data["data"]["attributes"]["resolution_message"] = resolution_message

        await self._client.update_incident(incident_id, update_data)

    @tool()
    async def mitigate_incident(self, incident_id: str) -> None:
        """Mitigate a Rootly incident

        Args:
            incident_id (str): The ID of the Rootly incident to mitigate
        """
        update_data = {
            "data": {"type": "incidents", "id": incident_id, "attributes": {"status": "mitigated"}}
        }
        await self._client.update_incident(incident_id, update_data)

    @tool()
    async def acknowledge_incident(self, incident_id: str) -> None:
        """Acknowledge a Rootly incident (moves to in_triage status)

        Args:
            incident_id (str): The ID of the Rootly incident to acknowledge

        Note: Sets status to 'in_triage' as this represents acknowledgment
        in the Rootly workflow.
        """
        update_data = {
            "data": {"type": "incidents", "id": incident_id, "attributes": {"status": "in_triage"}}
        }
        await self._client.update_incident(incident_id, update_data)

    async def get_incident_by_id(self, incident_id: str) -> RootlyIncident:
        """Get a single incident by its id

        Args:
            incident_id (str): The Rootly ID of the incident

        Returns:
            RootlyIncident: the rootly incident data
        """
        response = await self._client.get_incident(incident_id)
        return RootlyIncident(**response["data"])

    async def recent_incident_payloads(
        self, since: AwareDatetime | None = None, sort: str = "-created_at"
    ) -> AsyncGenerator[RootlyIncidentPayload, None]:
        """Get a list of recent Rootly incidents.

        Returns:
            AsyncGenerator: incident JSON payloads that can be used for demoing and testing agents
        """
        params = {
            "sort": sort,
            "page[size]": 100,
        }
        if since:
            params["filter[created_at][gte]"] = since.isoformat()

        response = await self._client.list_incidents(params)

        for incident_data in response.get("data", []):
            yield RootlyIncidentPayload(incident=RootlyIncident(**incident_data))

    async def populate_graph(self, graph: Graph) -> None:
        """Populate the graph with Rootly incidents."""
        # Get recent incidents and add them to the graph
        async for incident_payload in self.recent_incident_payloads():
            incident = incident_payload.incident
            from unpage.plugins.rootly.nodes import RootlyIncident

            # Create a Rootly incident node
            incident_node = RootlyIncident(
                node_id=f"rootly_incident:{incident.id}",
                raw_data=incident.model_dump(),
                _graph=graph,
            )
            await graph.add_node(incident_node)
