from typing import Any

import httpx


class RootlyClient:
    """Client for interacting with the Rootly API."""

    def __init__(self, api_key: str, base_url: str = "https://api.rootly.com/v1") -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/vnd.api+json",
            "Accept": "application/vnd.api+json",
        }

    async def _request(
        self, method: str, endpoint: str, json_data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Make an HTTP request to the Rootly API."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=url,
                headers=self.headers,
                json=json_data,
            )
            response.raise_for_status()
            return response.json()

    async def get_incident(self, incident_id: str) -> dict[str, Any]:
        """Get a specific incident by ID."""
        return await self._request("GET", f"/incidents/{incident_id}")

    async def list_incidents(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """List incidents with optional filtering parameters."""
        if params:
            url = "/incidents?" + "&".join(f"{k}={v}" for k, v in params.items())
        else:
            url = "/incidents"
        return await self._request("GET", url)

    async def update_incident(self, incident_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update an incident."""
        return await self._request("PUT", f"/incidents/{incident_id}", json_data=data)

    async def create_incident_event(
        self, incident_id: str, event_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Create an event (like a status update) for an incident."""
        return await self._request(
            "POST", f"/incidents/{incident_id}/incident_events", json_data=event_data
        )

    async def get_incident_events(self, incident_id: str) -> dict[str, Any]:
        """Get events for an incident."""
        return await self._request("GET", f"/incidents/{incident_id}/incident_events")

    async def mitigate_incident(self, incident_id: str) -> dict[str, Any]:
        """Mitigate an incident."""
        return await self._request("POST", f"/incidents/{incident_id}/mitigate")

    async def acknowledge_incident(self, incident_id: str) -> dict[str, Any]:
        """Acknowledge an incident."""
        return await self._request("POST", f"/incidents/{incident_id}/acknowledge")

    async def resolve_incident(self, incident_id: str) -> dict[str, Any]:
        """Resolve an incident."""
        return await self._request("POST", f"/incidents/{incident_id}/resolve")
