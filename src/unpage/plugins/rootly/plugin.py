import os
from typing import Any, cast
from collections.abc import AsyncGenerator

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
            raise LookupError(
                "plugins.rootly.settings.api_key (or $ROOTLY_API_KEY) must be set"
            )
        # Test API connectivity
        await self._client.list_incidents({"page[size]": "1"})

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
    async def post_status_update(self, incident_id: str, message: str) -> None:
        """Post a status update to a Rootly incident

        Args:
            incident_id (str): The Rootly ID of the incident
            message (str): The message to post
        """
        await self._client.create_incident_event(
            incident_id,
            {
                "data": {
                    "type": "incident_events",
                    "attributes": {
                        "kind": "status_update",
                        "description": message,
                    },
                }
            },
        )

    @tool()
    async def resolve_incident(
        self, incident_id: str, resolution_message: str | None = None
    ) -> None:
        """Resolve a Rootly incident

        Args:
            incident_id (str): The ID of the Rootly incident to resolve
            resolution_message (str, optional): A message to include with the resolution
        """
        # Resolve the incident
        await self._client.resolve_incident(incident_id)

        # If a resolution message was provided, add it as a status update
        if resolution_message:
            await self.post_status_update(incident_id, resolution_message)

    @tool()
    async def mitigate_incident(self, incident_id: str) -> None:
        """Mitigate a Rootly incident

        Args:
            incident_id (str): The ID of the Rootly incident to mitigate
        """
        await self._client.mitigate_incident(incident_id)

    @tool()
    async def acknowledge_incident(self, incident_id: str) -> None:
        """Acknowledge a Rootly incident

        Args:
            incident_id (str): The ID of the Rootly incident to acknowledge
        """
        await self._client.acknowledge_incident(incident_id)

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
            from unpage.knowledge import Node

            # Create a simple incident node
            incident_node = Node(
                node_id=f"rootly_incident:{incident.id}",
                raw_data=incident.model_dump(),
                _graph=graph,
            )
            await graph.add_node(incident_node)