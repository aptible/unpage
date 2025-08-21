import os
from datetime import UTC, datetime, timedelta
from typing import Any

import questionary
from pydantic import AwareDatetime, BaseModel

from unpage.config.utils import PluginSettings
from unpage.plugins.base import Plugin
from unpage.plugins.mixins import McpServerMixin, tool
from unpage.plugins.solarwinds.client import SolarWindsClient, SolarWindsLogEvent

RESULT_LIMIT = 75 * 1024


class SolarWindsSearchResult(BaseModel):
    """Result of a SolarWinds log search."""

    """True when the search results were truncated due to the response size limit or single search time limit"""
    truncated: bool = False
    """True when the search timed out due to the overall time limit"""
    timed_out: bool = False
    """The log events that were found"""
    results: list[SolarWindsLogEvent]


class SolarWindsPlugin(Plugin, McpServerMixin):
    _client: SolarWindsClient

    def __init__(
        self,
        *args: Any,
        token: str | None = None,
        datacenter: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.token = (
            token
            or os.environ.get("SOLARWINDS_API_TOKEN", "")
            or os.environ.get("SOLARWINDS_TOKEN", "")
        )
        self.datacenter = datacenter or os.environ.get("SOLARWINDS_DATACENTER", "") or "na-01"
        if self.token:
            self._client = SolarWindsClient(token=self.token, datacenter=self.datacenter)

    async def validate_plugin_config(self) -> None:
        await super().validate_plugin_config()
        await self._client.verify_connection()

    async def interactive_configure(self) -> PluginSettings:
        """Interactive wizard for configuring the settings of this plugin."""
        return {
            "token": await questionary.password(
                "Enter your SolarWinds API token",
                default=self.token,
                instruction="Generate API Access Token https://documentation.solarwinds.com/en/success_center/observability/content/settings/api-tokens.htm",
            ).unsafe_ask_async(),
            "datacenter": await questionary.text(
                "Enter your datacenter (na-01, na-02, eu-01, ap-01, etc.)",
                default="na-01",
                instruction="Your SolarWinds datacenter code https://documentation.solarwinds.com/en/success_center/observability/content/system_requirements/endpoints.htm#Find",
            ).unsafe_ask_async(),
        }

    @tool()
    async def search_logs(
        self,
        query: str,
        min_time: AwareDatetime,
        max_time: AwareDatetime,
        timeout_seconds: int = 10,
    ) -> SolarWindsSearchResult | str:
        """Search SolarWinds for logs within a given time range

        Args:
            query (str): The search query.
            min_time (AwareDatetime): The starting time for the range within which to search.
            max_time (AwareDatetime): The ending time for the range within which to search.
            timeout_seconds (int): The maximum seconds to wait for the search to complete. Defaults to 10 seconds.

        Returns:
            SolarWindsSearchResult: logs that matched the query and fit within response limit
        """
        if min_time >= max_time:
            return f"min_time must come before max_time {min_time=} {max_time=}"
        logs = []
        truncated = False
        content_length = 0

        class timeoutTracker:
            timed_out: bool = False
            start_time: AwareDatetime = datetime.now(UTC)
            time_out: timedelta = timedelta(seconds=timeout_seconds)

            def under_time_out(self, _: AwareDatetime | None) -> bool:
                self.timed_out = (datetime.now(UTC) - self.start_time) > self.time_out
                return not self.timed_out

        tt = timeoutTracker()
        async for log in self._client.search(
            query=query,
            min_time=min_time,
            max_time=max_time,
            continue_search=tt.under_time_out,
        ):
            message = log.model_dump_json(indent=6, include={"time", "message"})
            content_length += len(message) + 8
            if content_length >= RESULT_LIMIT:
                truncated = True
                break
            logs.append(message)
        return SolarWindsSearchResult(
            results=logs,
            truncated=truncated,
            timed_out=tt.timed_out,
        )
