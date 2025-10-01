from pydantic import AwareDatetime

from unpage.knowledge import HasMetrics
from unpage.models import Observation
from unpage.plugins.gcp.nodes.base import GcpNode


class GcpComputeInstance(GcpNode, HasMetrics):
    """A Google Compute Engine instance."""

    async def get_identifiers(self) -> list[str | None]:
        return [
            *await super().get_identifiers(),
            self.raw_data.get("id"),
            self.raw_data.get("name"),
            *(
                interface.get("networkIP")
                for interface in self.raw_data.get("networkInterfaces", [])
            ),
            *(
                config.get("natIP")
                for interface in self.raw_data.get("networkInterfaces", [])
                for config in interface.get("accessConfigs", [])
            ),
        ]

    async def get_reference_identifiers(
        self,
    ) -> list[str | None | tuple[str | None, str]]:
        references = [*await super().get_reference_identifiers()]

        # Add disk references
        for disk in self.raw_data.get("disks", []):
            source = disk.get("source")
            if source:
                # Extract disk name from URL
                disk_name = source.split("/")[-1]
                references.append((disk_name, "has_disk"))

        return references

    async def list_available_metrics(self) -> list[str]:
        return [
            "cpu/utilization",
            "network/received_bytes_count",
            "network/sent_bytes_count",
            "disk/read_bytes_count",
            "disk/write_bytes_count",
        ]

    async def get_metric(
        self,
        metric_name: str,
        time_range_start: AwareDatetime,
        time_range_end: AwareDatetime,
    ) -> list[Observation] | str:
        """Get metrics for the Compute Engine instance."""
        zone = self.raw_data.get("zone", "").split("/")[-1]
        instance_id = self.raw_data.get("id")

        if not zone or not instance_id:
            return "Missing zone or instance ID"

        return await self._get_cloud_monitoring_metric(
            metric_type=f"compute.googleapis.com/instance/{metric_name}",
            resource_type="gce_instance",
            resource_labels={
                "project_id": self.project_id,
                "zone": zone,
                "instance_id": str(instance_id),
            },
            time_range_start=time_range_start,
            time_range_end=time_range_end,
            aggregation_period=300,
        )
