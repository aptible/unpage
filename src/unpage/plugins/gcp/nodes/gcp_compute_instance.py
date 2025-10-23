"""Google Compute Engine instance node."""

from typing import TYPE_CHECKING

from unpage.knowledge import HasLogs, HasMetrics
from unpage.models import LogLine, Observation
from unpage.plugins.gcp.nodes.base import GcpNode

if TYPE_CHECKING:
    from pydantic import AwareDatetime


class GcpComputeInstance(GcpNode, HasMetrics, HasLogs):
    """A Google Compute Engine VM instance."""

    async def get_identifiers(self) -> list[str | None]:
        """Get unique identifiers for this instance."""
        identifiers = await super().get_identifiers()

        # Add instance-specific identifiers
        identifiers.extend(
            [
                self.raw_data.get("id"),  # Numeric instance ID
                self.raw_data.get("name"),  # Instance name
                self.raw_data.get("selfLink"),  # Full resource URL
            ]
        )

        # Add network interfaces
        for interface in self.raw_data.get("networkInterfaces", []):
            identifiers.append(interface.get("networkIP"))  # Internal IP
            for access_config in interface.get("accessConfigs", []):
                identifiers.append(access_config.get("natIP"))  # External IP

        return identifiers

    async def get_reference_identifiers(self) -> list[str | None | tuple[str | None, str]]:
        """Get identifiers that reference other resources."""
        refs = await super().get_reference_identifiers()

        # Add disk references
        for disk in self.raw_data.get("disks", []):
            if disk.get("source"):
                # Extract disk name from source URL
                disk_id = disk["source"].split("/")[-1]
                refs.append((disk_id, "has_disk"))

        # Add network/subnet references
        for interface in self.raw_data.get("networkInterfaces", []):
            if interface.get("network"):
                network_id = interface["network"].split("/")[-1]
                refs.append((network_id, "in_network"))

            if interface.get("subnetwork"):
                subnet_id = interface["subnetwork"].split("/")[-1]
                refs.append((subnet_id, "in_subnet"))

        # Add instance group references
        # Note: This would require additional API calls to determine membership
        # For now, we'll skip this

        return refs

    async def list_available_metrics(self) -> list[str]:
        """List available Cloud Monitoring metrics for this instance."""
        return [
            "compute.googleapis.com/instance/cpu/utilization",
            "compute.googleapis.com/instance/cpu/usage_time",
            "compute.googleapis.com/instance/disk/read_bytes_count",
            "compute.googleapis.com/instance/disk/write_bytes_count",
            "compute.googleapis.com/instance/disk/read_ops_count",
            "compute.googleapis.com/instance/disk/write_ops_count",
            "compute.googleapis.com/instance/network/received_bytes_count",
            "compute.googleapis.com/instance/network/sent_bytes_count",
            "compute.googleapis.com/instance/network/received_packets_count",
            "compute.googleapis.com/instance/network/sent_packets_count",
            "compute.googleapis.com/instance/memory/balloon/ram_used",
            "compute.googleapis.com/instance/memory/balloon/ram_size",
        ]

    async def get_metric(
        self,
        metric_name: str,
        time_range_start: "AwareDatetime",
        time_range_end: "AwareDatetime",
    ) -> list[Observation] | str:
        """Get metrics from Cloud Monitoring for this instance."""

        # Extract zone from the instance data
        zone_url = self.raw_data.get("zone", "")
        zone = zone_url.split("/")[-1] if zone_url else ""

        # Build resource labels for this instance
        resource_labels = {
            "instance_id": str(self.raw_data.get("id", "")),
            "zone": zone,
            "project_id": self.project_id,
        }

        return await self._get_cloud_monitoring_metrics(
            metric_type=metric_name,
            resource_type="gce_instance",
            resource_labels=resource_labels,
            start_time=time_range_start,
            end_time=time_range_end,
        )

    async def get_logs(
        self,
        time_range_start: "AwareDatetime",
        time_range_end: "AwareDatetime",
    ) -> list[LogLine]:
        """Get logs from Cloud Logging for this instance."""

        instance_id = self.raw_data.get("id", "")

        # Build filter for this specific instance
        filter_str = f'resource.type="gce_instance" AND resource.labels.instance_id="{instance_id}"'

        logs = await self._get_cloud_logging_logs(
            start_time=time_range_start,
            end_time=time_range_end,
            filter_str=filter_str,
            max_entries=100,
        )

        # Format logs as LogLine objects
        from datetime import datetime

        return [
            LogLine(
                time=datetime.fromisoformat(entry.get("timestamp", "")),
                log=f"[{entry.get('severity', 'INFO')}] {entry.get('textPayload') or str(entry.get('jsonPayload', {}))}",
            )
            for entry in logs
            if entry.get("timestamp")
        ]

    @property
    def display_name(self) -> str:
        """Get a human-readable display name for this instance."""
        return self.raw_data.get("name", "Unknown GCE Instance")

    @property
    def status(self) -> str:
        """Get the current status of the instance."""
        return self.raw_data.get("status", "UNKNOWN")

    @property
    def machine_type(self) -> str:
        """Get the machine type of the instance."""
        machine_type_url = self.raw_data.get("machineType", "")
        return machine_type_url.split("/")[-1] if machine_type_url else "unknown"

    @property
    def zone(self) -> str:
        """Get the zone where the instance is located."""
        zone_url = self.raw_data.get("zone", "")
        return zone_url.split("/")[-1] if zone_url else "unknown"
