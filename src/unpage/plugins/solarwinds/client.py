from collections.abc import AsyncGenerator, Callable
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
from pydantic import AwareDatetime, BaseModel, ConfigDict


class SolarWindsLogEvent(BaseModel):
    model_config = ConfigDict(
        extra="ignore",  # ignore fields in API results we don't need
    )

    """time that SolarWinds received the log event (ISO 8601 timestamp)"""
    time: AwareDatetime

    """log event message"""
    message: str


class ResultPageInfo(BaseModel):
    """Pagination links"""

    prevPage: str | None = None
    nextPage: str | None = None


class SearchResult(BaseModel):
    """Search result from SolarWinds API"""

    """An array of hashes of log events (one hash per event)"""
    logs: list[SolarWindsLogEvent]

    pageInfo: ResultPageInfo


class SolarWindsClient(httpx.AsyncClient):
    """SolarWinds API client

    https://api.na-01.cloud.solarwinds.com/v1/#/logs/searchLogs
    """

    BASE_URL_FORMAT = "https://api.{datacenter}.cloud.solarwinds.com"

    def __init__(self, token: str, datacenter: str, connection_limit: int = 10) -> None:
        self._token = token
        base_url = self.BASE_URL_FORMAT.format(datacenter=datacenter)
        super().__init__(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {self._token}",
            },
            timeout=httpx.Timeout(60),
            limits=httpx.Limits(max_connections=connection_limit),
        )

    async def verify_connection(self) -> None:
        response = await self.get("/v1/logs", params={"pageSize": 1})
        response.raise_for_status()
        SearchResult.model_validate(response.json())

    @staticmethod
    def extract_skip_token(path: str) -> str | None:
        """Extract the skipToken parameter from the search result.

        Args:
          path: The URL path string, returned by the Solarwinds search result
          e.g. "/v1/logs?filter=test&skipToken=ABC123&direction=backward"

        Returns:
          The skipToken value, or None
        """
        parsed_url = urlparse(path)
        query_params = parse_qs(parsed_url.query)
        skip_tokens = query_params.get("skipToken", [])
        return skip_tokens[0] if skip_tokens else None

    async def search(
        self,
        query: str,
        min_time: AwareDatetime,
        max_time: AwareDatetime,
        page_size: int = 1000,
        continue_search: Callable[[], bool] | None = None,
    ) -> AsyncGenerator[SolarWindsLogEvent, None]:
        """Search logs with pagination.

        Args:
            query: The search filter string
            min_time: Start time for the search
            max_time: End time for the search
            page_size: Number of results per page

        Yields:
            Log events matching the search criteria
        """
        skip_token = None

        while True:
            params: dict[str, Any] = {
                "filter": query,
                "startTime": min_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "endTime": max_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "pageSize": page_size,
                "direction": "backward",
            }

            if skip_token:
                params["skipToken"] = skip_token

            response = await self.get("/v1/logs", params=params)
            response.raise_for_status()
            result = SearchResult(**response.json())

            # Yield all logs in the current page
            for log in result.logs:
                yield log

            # Check if we have a next page
            if hasattr(result.pageInfo, "nextPage") and result.pageInfo.nextPage:
                new_token = self.extract_skip_token(result.pageInfo.nextPage)
                if not new_token or new_token == skip_token:
                    break
                skip_token = new_token
            else:
                break
            if continue_search is None or not continue_search():
                break
