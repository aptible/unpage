import os
from datetime import UTC, datetime, timedelta
from typing import Any

import anyio
import questionary
from pydantic import AwareDatetime

from unpage.config import PluginSettings
from unpage.knowledge import Graph
from unpage.plugins.base import Plugin
from unpage.plugins.datadog.client import DatadogClient
from unpage.plugins.datadog.models import DatadogLogSearchResult
from unpage.plugins.datadog.nodes.datadog_api import DatadogApi
from unpage.plugins.datadog.nodes.datadog_service import DatadogService
from unpage.plugins.datadog.nodes.datadog_system import DatadogSystem
from unpage.plugins.datadog.nodes.datadog_team import DatadogTeam
from unpage.plugins.mixins import KnowledgeGraphMixin, tool
from unpage.plugins.mixins.mcp import McpServerMixin

RESULT_LIMIT = 75 * 1024


class DatadogPlugin(Plugin, KnowledgeGraphMixin, McpServerMixin):
    """A plugin for Datadog."""

    _client: DatadogClient

    def __init__(
        self,
        *args: Any,
        api_key: str | None = None,
        application_key: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._api_key = api_key
        self._application_key = application_key
        self._client = DatadogClient(
            api_key=api_key or os.getenv("DATADOG_API_KEY", ""),
            application_key=application_key or os.getenv("DATADOG_APP_KEY", ""),
        )

    async def interactive_configure(self) -> PluginSettings:
        """Interactive wizard for configuring the settings of this plugin."""
        return {
            "api_key": await questionary.password(
                "Enter your Datadog API key",
                default=self._api_key or os.getenv("DATADOG_API_KEY", ""),
                instruction="Generate an API key with https://docs.unpage.ai/plugins/datadog#prerequisites",
            ).unsafe_ask_async(),
            "application_key": await questionary.password(
                "Enter your Datadog application key",
                default=self._application_key or os.getenv("DATADOG_APP_KEY", ""),
                instruction="Generate an application key with https://docs.unpage.ai/plugins/datadog#prerequisites",
            ).unsafe_ask_async(),
        }

    async def populate_graph(self, graph: Graph) -> None:
        """Populate the graph with Datadog entities."""
        async with anyio.create_task_group() as tg:
            tg.start_soon(self._populate_teams, graph)
            tg.start_soon(self._populate_software_catalog_entities, graph)

    async def _populate_teams(self, graph: Graph) -> None:
        async for team in self._client.iter_teams():
            await graph.add_node(
                DatadogTeam(
                    node_id=f"team:default/{team['attributes']['handle']}",
                    raw_data=team.to_dict(),
                    _graph=graph,
                )
            )

    async def _populate_software_catalog_entities(self, graph: Graph) -> None:
        async for entity in self._client.iter_software_catalog_entities():
            entity_kind = entity["attributes"]["kind"]

            if entity_kind == "service":
                node = DatadogService(
                    node_id=f"service:default/{entity['attributes']['name']}",
                    raw_data=entity.to_dict(),
                    _graph=graph,
                )
            elif entity_kind == "api":
                node = DatadogApi(
                    node_id=f"api:default/{entity['attributes']['name']}",
                    raw_data=entity.to_dict(),
                    _graph=graph,
                )
            else:
                raise ValueError(f"Unknown entity kind: {entity_kind}")

            await graph.add_node(node)

            # HACK: There doesn't seem to be a way to list systems directly in datadog, so we'll fake it for now.
            for (
                related_entity_reference,
                _,
            ) in await node._get_related_entity_reference_identifiers():
                if related_entity_reference.startswith("system:"):
                    await graph.add_node(
                        DatadogSystem(
                            node_id=related_entity_reference,
                            raw_data={
                                "attributes": {
                                    "name": related_entity_reference.split("/")[-1],
                                },
                            },
                            _graph=graph,
                        )
                    )

    @tool()
    async def search_logs(
        self,
        query: str,
        min_time: AwareDatetime,
        max_time: AwareDatetime,
    ) -> DatadogLogSearchResult | str:
        """Search Datadog for logs within a given time range

        Args:
            query (str): The search query.
            min_time (AwareDatetime): The starting time for the range within which to search.
            max_time (AwareDatetime): The ending time for the range within which to search.

        Returns:
            DatadogLogSearchResult: logs that matched the query and fit within response limit
        """
        if min_time >= max_time:
            return f"min_time must come before max_time {min_time=} {max_time=}"
        logs = []
        truncated = False
        content_length = 0

        class timeoutTracker:
            timed_out: bool = False
            start_time: AwareDatetime = datetime.now(UTC)

            def under_time_out(self, _: AwareDatetime | None) -> bool:
                self.timed_out = (datetime.now(UTC) - self.start_time) > timedelta(seconds=10)
                return not self.timed_out

        tt = timeoutTracker()
        async for log in self._client.search_logs(
            query=query if ":" in query else f"*:*{query}*",
            min_time=min_time,
            max_time=max_time,
            continue_search=tt.under_time_out,
        ):
            content_length += len(log.model_dump_json(indent=6)) + 8
            if content_length >= RESULT_LIMIT:
                truncated = True
                break
            logs.append(log)
        return DatadogLogSearchResult(
            results=logs,
            truncated=truncated or tt.timed_out,
        )
