from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING

from google.auth import default as get_default_credentials
from google.cloud import monitoring_v3
from pydantic import BaseModel, Field

from unpage.knowledge import Node
from unpage.models import Observation

if TYPE_CHECKING:
    from google.auth.credentials import Credentials
    from pydantic import AwareDatetime


DEFAULT_GCP_PROJECT_NAME = "default"


class GcpProject(BaseModel):
    name: str | None = Field(default=DEFAULT_GCP_PROJECT_NAME)
    project_id: str | None = Field(default=None)
    credentials_path: str | None = Field(default=None)

    @property
    def credentials(self) -> "Credentials":
        """Get Google Cloud credentials."""
        if not hasattr(self, "_credentials"):
            if self.credentials_path:
                import os

                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.credentials_path
            credentials, project = get_default_credentials()
            if not self.project_id:
                self.project_id = project
            self._credentials = credentials
        return self._credentials

    @property
    def effective_project_id(self) -> str:
        """Get the effective project ID."""
        if self.project_id:
            return self.project_id
        # Trigger credentials loading to get project ID
        try:
            _ = self.credentials
        except Exception:
            # If credentials fail to load, return a placeholder
            # This allows plugin to be registered even without credentials
            return "unknown-project"
        if not self.project_id:
            # Set a default if still not available
            self.project_id = "unknown-project"
        return self.project_id


class GcpNode(Node):
    """A base class for all GCP nodes."""

    gcp_project: GcpProject = Field()

    @property
    def credentials(self) -> "Credentials":
        if not hasattr(self, "_credentials"):
            self._credentials = self.gcp_project.credentials
        return self._credentials

    @property
    def project_id(self) -> str:
        return self.gcp_project.effective_project_id

    async def _get_cloud_monitoring_metric(
        self,
        metric_type: str,
        resource_type: str,
        resource_labels: dict[str, str],
        time_range_start: "AwareDatetime",
        time_range_end: "AwareDatetime",
        aggregation_period: int = 300,
    ) -> list[Observation]:
        """
        Get metrics from Google Cloud Monitoring.

        Args:
            metric_type: The metric type (e.g., 'compute.googleapis.com/instance/cpu/utilization')
            resource_type: The resource type (e.g., 'gce_instance')
            resource_labels: Labels to filter the resource
            time_range_start: Start time for the metric query
            time_range_end: End time for the metric query
            aggregation_period: Aggregation period in seconds (default: 300)

        Returns:
            List of Observation objects containing the metric data
        """
        client = monitoring_v3.MetricServiceClient(credentials=self.credentials)
        project_name = f"projects/{self.project_id}"

        # Build the filter
        filter_parts = [f'metric.type = "{metric_type}"', f'resource.type = "{resource_type}"']
        for label_key, label_value in resource_labels.items():
            filter_parts.append(f'resource.labels.{label_key} = "{label_value}"')
        filter_string = " AND ".join(filter_parts)

        # Create the time interval
        interval = monitoring_v3.TimeInterval(
            {
                "end_time": {"seconds": int(time_range_end.timestamp())},
                "start_time": {"seconds": int(time_range_start.timestamp())},
            }
        )

        # Create aggregation
        aggregation = monitoring_v3.Aggregation(
            {
                "alignment_period": {"seconds": aggregation_period},
                "per_series_aligner": monitoring_v3.Aggregation.Aligner.ALIGN_MEAN,
            }
        )

        # Make the request
        results = client.list_time_series(
            request={
                "name": project_name,
                "filter": filter_string,
                "interval": interval,
                "aggregation": aggregation,
            }
        )

        observations: list[Observation] = []
        series: defaultdict[str, dict[datetime, float]] = defaultdict(dict)

        for result in results:
            metric_kind = result.metric.type.split("/")[-1]
            for point in result.points:
                dt = point.interval.end_time
                # Handle different value types
                if point.value.HasField("double_value"):
                    value = point.value.double_value
                elif point.value.HasField("int64_value"):
                    value = float(point.value.int64_value)
                elif point.value.HasField("bool_value"):
                    value = float(point.value.bool_value)
                else:
                    continue

                series[metric_kind][dt] = value

        # Convert series to Observations
        for metric_name, data in series.items():
            observations.append(
                Observation(
                    node_id=self.nid,
                    observation_type=metric_name,
                    data=data,
                )
            )

        return observations
