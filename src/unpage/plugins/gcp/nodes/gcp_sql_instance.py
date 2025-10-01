from pydantic import AwareDatetime

from unpage.knowledge import HasMetrics
from unpage.models import Observation
from unpage.plugins.gcp.nodes.base import GcpNode


class GcpSqlInstance(GcpNode, HasMetrics):
    """A Google Cloud SQL instance."""

    async def get_identifiers(self) -> list[str | None]:
        identifiers = [
            *await super().get_identifiers(),
            self.raw_data.get("name"),
            self.raw_data.get("connectionName"),
        ]

        # Add IP addresses
        for ip_mapping in self.raw_data.get("ipAddresses", []):
            identifiers.append(ip_mapping.get("ipAddress"))

        return identifiers

    async def get_reference_identifiers(
        self,
    ) -> list[str | None | tuple[str | None, str]]:
        return [*await super().get_reference_identifiers()]

    async def list_available_metrics(self) -> list[str]:
        return [
            "cpu/utilization",
            "memory/utilization",
            "disk/utilization",
            "network/received_bytes_count",
            "network/sent_bytes_count",
        ]

    async def get_metric(
        self,
        metric_name: str,
        time_range_start: AwareDatetime,
        time_range_end: AwareDatetime,
    ) -> list[Observation] | str:
        """Get metrics for the Cloud SQL instance."""
        database_id = self.raw_data.get("name")

        if not database_id:
            return "Missing database ID"

        return await self._get_cloud_monitoring_metric(
            metric_type=f"cloudsql.googleapis.com/database/{metric_name}",
            resource_type="cloudsql_database",
            resource_labels={
                "project_id": self.project_id,
                "database_id": database_id,
            },
            time_range_start=time_range_start,
            time_range_end=time_range_end,
            aggregation_period=300,
        )
