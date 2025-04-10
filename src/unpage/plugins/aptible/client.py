import base64
import json
import os
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import anyio
import httpx
from pydantic import AwareDatetime

from unpage.models import Observation
from unpage.utils import as_completed


class AptibleClient(httpx.AsyncClient):
    """A client for the Aptible API."""

    BASE_API_URL = "https://api.aptible.com"
    BASE_AUTH_URL = "https://auth.aptible.com"

    TOKENS_PATH = Path("~/.aptible/tokens.json").expanduser()

    def __init__(
        self,
        api_key: str | None = None,
        connection_limit: int = 100,
        base_url: str = BASE_API_URL,
    ) -> None:
        self._jwt = api_key

        super().__init__(
            base_url=base_url,
            headers={
                "Content-Type": "application/json; charset=utf-8",
            },
            timeout=httpx.Timeout(None),
            limits=httpx.Limits(max_connections=connection_limit),
        )

    async def request(self, *args: Any, **kwargs: Any) -> httpx.Response:
        return await super().request(
            *args,
            **{
                **kwargs,
                "headers": {
                    # Inject the API key into the headers.
                    "Authorization": f"Bearer {await self.get_api_key()}",
                    **(kwargs["headers"] or {}),
                },
            },
        )

    async def get_api_key(self) -> str:
        # TODO: Check for expiry and refresh if necessary
        if not self._jwt or await self.jwt_expired(self._jwt):
            if "APTIBLE_EMAIL" in os.environ and "APTIBLE_PASSWORD" in os.environ:
                self._jwt = await self.authorize(
                    email=os.environ["APTIBLE_EMAIL"],
                    password=os.environ["APTIBLE_PASSWORD"],
                )
            elif self.TOKENS_PATH.exists():
                tokens = json.loads(self.TOKENS_PATH.read_text().strip())
                self._jwt = tokens[self.BASE_AUTH_URL]
            else:
                raise ValueError("No API key found")
        return self._jwt

    async def authorize(self, email: str, password: str) -> str:
        async with httpx.AsyncClient(base_url=self.BASE_AUTH_URL) as auth_client:
            resp = await auth_client.post(
                f"{self.BASE_AUTH_URL}/tokens",
                json={
                    "username": email,
                    "password": password,
                    "grant_type": "password",
                    "scope": "manage",
                    "expires_in": 3600,
                },
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            # TODO: Special error messaging for 401s caused by MFA requirements.
            resp.raise_for_status()
            return resp.json()["access_token"]

    async def jwt_expired(self, jwt: str) -> bool:
        # Decode the JWT token
        decoded = jwt.split(".")[1]
        # Add padding if needed for base64 decoding
        decoded += "=" * ((4 - len(decoded) % 4) % 4)
        decoded = base64.b64decode(decoded).decode()
        decoded = json.loads(decoded)
        # Check if the JWT is expired, or will expire in the next 60 seconds.
        return int(decoded["exp"]) < (time.time() - 60)

    async def validate_auth(self) -> None:
        resp = await self.get(f"{self.BASE_AUTH_URL}/organizations")
        try:
            resp.raise_for_status()
        except Exception as ex:
            raise ValueError(
                "Authentication invalid for Aptible API. Try running `aptible login` in another terminal, then try again here"
            ) from ex

    async def paginate(self, url: str) -> AsyncGenerator[dict[str, Any], None]:
        while url:
            response = await self.get(url)
            response.raise_for_status()
            for collection in response.json().get("_embedded", {}).values():
                for item in collection:
                    yield item
            url = response.json().get("_links", {}).get("next", {}).get("href")

    @asynccontextmanager
    async def concurrent_paginator(
        self, url: str
    ) -> AsyncGenerator[tuple[AsyncGenerator[dict[str, Any], None], int], None]:
        """Retrieve all results in parallel.

        Fetches the first page of results to get pagination information, and
        then fetches all subsequent pages in parallel, yielding items as they
        are available. Does NOT maintain result order.
        """
        first_page_response = await self.get(url)
        first_page_response.raise_for_status()

        first_page = first_page_response.json()
        total_count = first_page["total_count"]
        per_page = first_page["per_page"]
        total_pages = total_count // per_page

        async def item_generator() -> AsyncGenerator[dict[str, Any], None]:
            # Yield all results from the first page
            for collection in first_page["_embedded"].values():
                collection = collection if isinstance(collection, list) else [collection]
                for item in collection:
                    yield item

            # Fetch all subsequent pages in parallel
            pages = (self.get(f"{url}?page={p}") for p in range(1, total_pages + 1))
            try:
                async with anyio.create_task_group() as tg:
                    for page in as_completed(tg, pages):
                        try:
                            response = await page
                            response.raise_for_status()
                            for collection in response.json().get("_embedded", {}).values():
                                collection = (
                                    collection if isinstance(collection, list) else [collection]
                                )
                                for item in collection:
                                    yield item
                        except Exception as e:
                            print(f"Error processing page from {url}: {e}")
            except Exception as e:
                print(f"Error in concurrent iterator for {url}: {e}")

        yield (item_generator(), total_count)


class AptibleMetricsClient(AptibleClient):
    """A client for the Aptible Metrics API."""

    METRICS_BASE_URL = "https://metrictunnel-nextgen.aptible.com"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs, base_url=self.METRICS_BASE_URL)

    async def get_metrics(
        self,
        node_id: str,
        container_ids: list[int | str],
        metric: str,
        time_range_start: AwareDatetime,
        time_range_end: AwareDatetime,
    ) -> list[Observation]:
        ts = int(time_range_end.timestamp() * 1000)

        response = await self.get(
            f"/proxy/{':'.join(str(cid) for cid in container_ids)}",
            params={
                "horizon": "1h",
                "ts": ts,
                "metric": metric,
                "requestedTicks": 300,
            },
        )
        data = response.json()

        if "error" in data:
            print(f"Error retrieving metrics: {data['error']}")
            return []

        dates: list[AwareDatetime] = []
        value_columns: dict[str, list[float]] = {}

        # Split columns into dates and values
        for first_col, *other_cols in data.get("columns", []):
            if first_col == "time_0":
                dates = [
                    datetime.strptime(d, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
                    for d in other_cols
                ]
            else:
                value_columns[first_col] = other_cols

        # For each series, zip its values with the dates
        result = [
            Observation(
                node_id=node_id,
                observation_type=metric,
                data={
                    date: value
                    for date, value in zip(dates, values, strict=True)
                    if value is not None
                },
            )
            for values in value_columns.values()
        ]

        return result
