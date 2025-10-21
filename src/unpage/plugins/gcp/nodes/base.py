"""Base classes for GCP nodes."""

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast

import aiohttp
from google.auth import default, load_credentials_from_file
from google.auth.transport import requests
from pydantic import BaseModel, Field

from unpage.knowledge import Node
from unpage.models import Observation

if TYPE_CHECKING:
    from google.auth.credentials import Credentials
    from pydantic import AwareDatetime

DEFAULT_GCP_PROJECT_NAME = "default"


class GcpProject(BaseModel):
    """Configuration for a GCP project."""

    name: str = Field(default=DEFAULT_GCP_PROJECT_NAME)
    project_id: str | None = Field(default=None)
    auth_method: str = Field(default="adc")  # adc, service_account
    service_account_key_path: str | None = Field(default=None)
    regions: list[str] | None = Field(default=None)  # None means all regions

    def get_credentials(self) -> "Credentials":
        """Get GCP credentials based on configured auth method."""
        if self.auth_method == "service_account" and self.service_account_key_path:
            if not Path(self.service_account_key_path).exists():
                raise ValueError(
                    f"Service account key file not found: {self.service_account_key_path}"
                )
            credentials, _ = load_credentials_from_file(self.service_account_key_path)
            return credentials
        else:
            # Default to Application Default Credentials (ADC)
            # This will use credentials from: gcloud auth application-default login,
            # environment variables, or service accounts on GCP compute resources
            credentials, _ = default()
            return cast("Credentials", credentials)

    @property
    def credentials(self) -> "Credentials":
        """Cached credentials property."""
        if not hasattr(self, "_credentials"):
            self._credentials = self.get_credentials()
        return self._credentials


class GcpNode(Node):
    """Base class for all GCP nodes."""

    gcp_project: GcpProject = Field()

    @property
    def project_id(self) -> str:
        """Get the project ID for this node."""
        return self.gcp_project.project_id or self.raw_data.get("project_id", "")

    async def _get_access_token(self) -> str:
        """Get an access token for API calls."""
        credentials = self.gcp_project.credentials

        # Refresh the credentials if needed
        if not credentials.valid:
            request = requests.Request()
            credentials.refresh(request)

        return credentials.token or ""

    async def _make_api_request(
        self,
        url: str,
        method: str = "GET",
        params: dict | None = None,
        json_data: dict | None = None,
    ) -> dict:
        """Make an authenticated API request to GCP."""
        token = await self._get_access_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        async with (
            aiohttp.ClientSession() as session,
            session.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json_data,
            ) as response,
        ):
            if response.status >= 400:
                error_text = await response.text()
                raise Exception(f"GCP API error ({response.status}): {error_text}")
            return await response.json()

    async def _get_cloud_monitoring_metrics(
        self,
        metric_type: str,
        resource_type: str,
        resource_labels: dict,
        start_time: "AwareDatetime",
        end_time: "AwareDatetime",
    ) -> list[Observation]:
        """Get metrics from Cloud Monitoring (Stackdriver)."""
        project = self.project_id

        # Format timestamps for the API
        start_str = start_time.isoformat()
        end_str = end_time.isoformat()

        # Build the filter for the specific resource
        filter_parts = [
            f'metric.type="{metric_type}"',
            f'resource.type="{resource_type}"',
        ]
        for key, value in resource_labels.items():
            filter_parts.append(f'resource.labels.{key}="{value}"')

        filter_str = " AND ".join(filter_parts)

        url = f"https://monitoring.googleapis.com/v3/projects/{project}/timeSeries"
        params = {
            "filter": filter_str,
            "interval.startTime": start_str,
            "interval.endTime": end_str,
        }

        try:
            result = await self._make_api_request(url, params=params)
            observations = []

            for time_series in result.get("timeSeries", []):
                points = time_series.get("points", [])

                if not points:
                    continue

                # Extract the metric name
                metric_name = metric_type.split("/")[-1]

                # Group points by value type (GAUGE, DELTA, CUMULATIVE)
                data_points = {}
                for point in points:
                    interval = point.get("interval", {})
                    value = point.get("value", {})

                    # Get the timestamp
                    timestamp_str = interval.get("endTime")
                    if not timestamp_str:
                        continue

                    # Parse timestamp
                    timestamp = datetime.fromisoformat(timestamp_str)

                    # Extract the numeric value
                    numeric_value = None
                    if "doubleValue" in value:
                        numeric_value = float(value["doubleValue"])
                    elif "int64Value" in value:
                        numeric_value = int(value["int64Value"])
                    elif "boolValue" in value:
                        numeric_value = 1.0 if value["boolValue"] else 0.0

                    if numeric_value is not None:
                        data_points[timestamp] = numeric_value

                if data_points:
                    observations.append(
                        Observation(
                            node_id=self.nid,
                            observation_type=metric_name,
                            data=data_points,
                        )
                    )

            return observations

        except Exception:
            # Return empty list on error (similar to AWS plugin behavior)
            return []

    async def _get_cloud_logging_logs(
        self,
        start_time: "AwareDatetime",
        end_time: "AwareDatetime",
        filter_str: str | None = None,
        max_entries: int = 100,
    ) -> list[dict]:
        """Get logs from Cloud Logging."""
        project = self.project_id

        # Build the filter
        filters = []
        if filter_str:
            filters.append(filter_str)

        # Add time range
        start_str = start_time.isoformat()
        end_str = end_time.isoformat()
        filters.append(f'timestamp>="{start_str}"')
        filters.append(f'timestamp<="{end_str}"')

        final_filter = " AND ".join(filters) if filters else ""

        url = "https://logging.googleapis.com/v2/entries:list"
        body = {
            "resourceNames": [f"projects/{project}"],
            "filter": final_filter,
            "pageSize": min(max_entries, 1000),  # API max is 1000
            "orderBy": "timestamp desc",
        }

        try:
            result = await self._make_api_request(url, method="POST", json_data=body)
            return result.get("entries", [])
        except Exception:
            return []
