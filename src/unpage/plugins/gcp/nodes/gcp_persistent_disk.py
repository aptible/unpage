"""Google Compute Engine Persistent Disk node."""

from typing import TYPE_CHECKING

from unpage.knowledge import HasMetrics
from unpage.models import Observation
from unpage.plugins.gcp.nodes.base import GcpNode

if TYPE_CHECKING:
    from pydantic import AwareDatetime


class GcpPersistentDisk(GcpNode, HasMetrics):
    """A Google Compute Engine Persistent Disk."""

    async def get_identifiers(self) -> list[str | None]:
        """Get unique identifiers for this disk."""
        identifiers = await super().get_identifiers()

        # Add disk-specific identifiers
        identifiers.extend(
            [
                self.raw_data.get("id"),  # Numeric disk ID
                self.raw_data.get("name"),  # Disk name
                self.raw_data.get("selfLink"),  # Full resource URL
            ]
        )

        return identifiers

    async def get_reference_identifiers(self) -> list[str | None | tuple[str | None, str]]:
        """Get identifiers that reference other resources."""
        refs = await super().get_reference_identifiers()

        # Add references to instances that use this disk
        for user in self.raw_data.get("users", []):
            # Extract instance name from user URL
            instance_id = user.split("/")[-1]
            refs.append((instance_id, "attached_to"))

        # Add source image reference if this disk was created from an image
        source_image = self.raw_data.get("sourceImage")
        if source_image:
            image_id = source_image.split("/")[-1]
            refs.append((image_id, "created_from"))

        # Add source snapshot reference if this disk was created from a snapshot
        source_snapshot = self.raw_data.get("sourceSnapshot")
        if source_snapshot:
            snapshot_id = source_snapshot.split("/")[-1]
            refs.append((snapshot_id, "created_from"))

        return refs

    async def list_available_metrics(self) -> list[str]:
        """List available Cloud Monitoring metrics for this disk."""
        return [
            "compute.googleapis.com/instance/disk/read_bytes_count",
            "compute.googleapis.com/instance/disk/write_bytes_count",
            "compute.googleapis.com/instance/disk/read_ops_count",
            "compute.googleapis.com/instance/disk/write_ops_count",
            "compute.googleapis.com/instance/disk/throttled_read_bytes_count",
            "compute.googleapis.com/instance/disk/throttled_write_bytes_count",
        ]

    async def get_metric(
        self,
        metric_name: str,
        time_range_start: "AwareDatetime",
        time_range_end: "AwareDatetime",
    ) -> list[Observation] | str:
        """Get metrics from Cloud Monitoring for this disk."""

        # Extract zone from the disk data
        zone_url = self.raw_data.get("zone", "")
        zone = zone_url.split("/")[-1] if zone_url else ""

        # For disk metrics, we need to query by the instance it's attached to
        # Get the first user (instance) if available
        users = self.raw_data.get("users", [])
        if not users:
            return "Disk is not attached to any instance, metrics not available"

        # Extract instance ID from the user URL
        instance_url = users[0]
        instance_name = instance_url.split("/")[-1]

        # We need to get the instance ID, which requires knowing the instance details
        # For now, we'll use the disk device name as part of the metric filter
        disk_name = self.raw_data.get("name", "")

        resource_labels = {
            "instance_id": instance_name,  # This should ideally be the numeric ID
            "zone": zone,
            "project_id": self.project_id,
            "device_name": disk_name,
        }

        return await self._get_cloud_monitoring_metrics(
            metric_type=metric_name,
            resource_type="gce_instance",  # Disk metrics are reported through instance
            resource_labels=resource_labels,
            start_time=time_range_start,
            end_time=time_range_end,
        )

    @property
    def display_name(self) -> str:
        """Get a human-readable display name for this disk."""
        return self.raw_data.get("name", "Unknown Persistent Disk")

    @property
    def status(self) -> str:
        """Get the current status of the disk."""
        return self.raw_data.get("status", "UNKNOWN")

    @property
    def size_gb(self) -> int:
        """Get the size of the disk in GB."""
        return int(self.raw_data.get("sizeGb", 0))

    @property
    def disk_type(self) -> str:
        """Get the type of the disk."""
        type_url = self.raw_data.get("type", "")
        return type_url.split("/")[-1] if type_url else "unknown"

    @property
    def zone(self) -> str:
        """Get the zone where the disk is located."""
        zone_url = self.raw_data.get("zone", "")
        return zone_url.split("/")[-1] if zone_url else "unknown"

    @property
    def is_attached(self) -> bool:
        """Check if the disk is attached to any instance."""
        return bool(self.raw_data.get("users", []))
