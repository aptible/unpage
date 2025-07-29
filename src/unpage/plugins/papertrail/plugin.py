import os
from datetime import UTC, datetime, timedelta
from typing import Any

import questionary
from pydantic import AwareDatetime, BaseModel

from unpage.config.utils import PluginSettings
from unpage.plugins.base import Plugin
from unpage.plugins.mixins import McpServerMixin, tool
from unpage.plugins.papertrail.client import PapertrailClient, PapertrailLogEvent

RESULT_LIMIT = 9 * 1024


class PapertrailSearchResult(BaseModel):
    """Result of a Papertrail log search."""

    """True when the search results were truncated due to the response size limit or single search time limit"""
    truncated: bool = False
    """The log events that were found"""
    results: list[PapertrailLogEvent]


class PapertrailPlugin(Plugin, McpServerMixin):
    _client: PapertrailClient

    def __init__(
        self,
        *args: Any,
        token: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.token = (
            token
            or os.environ.get("PAPERTRAIL_API_TOKEN", "")
            or os.environ.get("PAPERTRAIL_TOKEN", "")
        )
        if self.token:
            self._client = PapertrailClient(token=self.token)

    async def validate_plugin_config(self) -> None:
        await super().validate_plugin_config()
        await self._client.verify_connection()

    async def interactive_configure(self) -> PluginSettings:
        """Interactive wizard for configuring the settings of this plugin."""
        return {
            "token": await questionary.password(
                "Enter your Papertrail API token",
                default=self.token
                or os.environ.get("PAPERTRAIL_API_TOKEN", "")
                or os.environ.get("PAPERTRAIL_TOKEN", ""),
            ).unsafe_ask_async(),
        }

    @tool()
    async def search_logs(
        self,
        query: str,
        min_time: AwareDatetime,
        max_time: AwareDatetime,
    ) -> PapertrailSearchResult | str:
        """Search Papertrail for logs within a given time range

        Args:
            query (str): The search query.
            min_time (AwareDatetime): The starting time for the range within which to search.
            max_time (AwareDatetime): The ending time for the range within which to search.

        Returns:
            PapertrailSearchResult: logs that matched the query and fit within response limit
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
        async for log in self._client.search(
            query=query,
            min_time=min_time,
            max_time=max_time,
            continue_search=tt.under_time_out,
        ):
            content_length += len(log.model_dump_json(indent=6)) + 8
            if content_length >= RESULT_LIMIT:
                truncated = True
                break
            logs.append(log)
        return PapertrailSearchResult(
            results=logs,
            truncated=truncated or tt.timed_out,
        )
