from pydantic import AwareDatetime

from unpage.knowledge import HasMetrics
from unpage.models import Observation

from .base import AzureNode


class AzureManagedDisk(AzureNode, HasMetrics):
    """An Azure Managed Disk."""

    async def get_identifiers(self) -> list[str | None]:
        identifiers = [
            *await super().get_identifiers(),
        ]

        if self.raw_data:
            # Add disk size as identifier
            disk_size_gb = self.raw_data.get("disk_size_gb")
            if disk_size_gb and self.resource_name:
                identifiers.append(f"{self.resource_name}-{disk_size_gb}GB")

            # Add disk type and size combination
            sku = self.raw_data.get("sku", {})
            sku_name = sku.get("name") if sku else None
            if sku_name and disk_size_gb:
                identifiers.append(f"{self.resource_name}-{sku_name}-{disk_size_gb}GB")

        return identifiers

    async def get_reference_identifiers(
        self,
    ) -> list[str | None | tuple[str | None, str]]:
        references = [
            *await super().get_reference_identifiers(),
        ]

        if self.raw_data:
            # Add attached VM reference
            managed_by = self.raw_data.get("managed_by")
            if managed_by:
                references.append((managed_by, "attached_to"))

            # Add disk access reference if available
            disk_access_id = self.raw_data.get("disk_access_id")
            if disk_access_id:
                references.append((disk_access_id, "uses_disk_access"))

        return references

    async def list_available_metrics(self) -> list[str]:
        """List available metrics for Azure Managed Disk."""
        return [
            "Composite Disk Read Bytes/sec",
            "Composite Disk Write Bytes/sec",
            "Composite Disk Read Operations/sec",
            "Composite Disk Write Operations/sec",
        ]

    async def get_metric(
        self,
        metric_name: str,
        time_range_start: AwareDatetime,
        time_range_end: AwareDatetime,
    ) -> list[Observation] | str:
        """Get specific metric data for this Azure Managed Disk."""
        return await self._get_azure_monitor_metrics(
            metric_names=[metric_name],
            aggregation="Average",
            start_time=time_range_start,
            end_time=time_range_end,
            interval="PT5M",  # 5 minute intervals
        )

    @property
    def sku_name(self) -> str:
        """Get the disk SKU name (Premium_LRS, Standard_LRS, etc.)."""
        sku = self.raw_data.get("sku", {}) if self.raw_data else {}
        return sku.get("name", "")

    @property
    def sku_tier(self) -> str:
        """Get the disk SKU tier."""
        sku = self.raw_data.get("sku", {}) if self.raw_data else {}
        return sku.get("tier", "")

    @property
    def disk_size_gb(self) -> int | None:
        """Get the disk size in GB."""
        size = self.raw_data.get("disk_size_gb") if self.raw_data else None
        return int(size) if size is not None else None

    @property
    def disk_size_bytes(self) -> int | None:
        """Get the disk size in bytes."""
        size = self.raw_data.get("disk_size_bytes") if self.raw_data else None
        return int(size) if size is not None else None

    @property
    def disk_state(self) -> str:
        """Get the disk state (Unattached, Attached, Reserved, etc.)."""
        return self.raw_data.get("disk_state", "") if self.raw_data else ""

    @property
    def creation_data(self) -> dict:
        """Get disk creation data."""
        return self.raw_data.get("creation_data", {}) if self.raw_data else {}

    @property
    def create_option(self) -> str:
        """Get the disk creation option (Empty, FromImage, Copy, etc.)."""
        creation_data = self.creation_data
        return creation_data.get("create_option", "")

    @property
    def source_uri(self) -> str:
        """Get the source URI if disk was created from another source."""
        creation_data = self.creation_data
        return creation_data.get("source_uri", "")

    @property
    def source_resource_id(self) -> str:
        """Get the source resource ID if disk was created from another Azure resource."""
        creation_data = self.creation_data
        return creation_data.get("source_resource_id", "")

    @property
    def provisioning_state(self) -> str:
        """Get the provisioning state."""
        return self.raw_data.get("provisioning_state", "") if self.raw_data else ""

    @property
    def time_created(self) -> str | None:
        """Get the disk creation time."""
        time_created = self.raw_data.get("time_created") if self.raw_data else None
        if time_created and hasattr(time_created, "isoformat"):
            return time_created.isoformat()
        return str(time_created) if time_created else None

    @property
    def managed_by(self) -> str:
        """Get the resource ID of the VM this disk is attached to (if any)."""
        return self.raw_data.get("managed_by", "") if self.raw_data else ""

    @property
    def is_attached(self) -> bool:
        """Check if the disk is attached to a VM."""
        return bool(self.managed_by)

    @property
    def os_type(self) -> str:
        """Get the OS type if this is an OS disk (Windows, Linux)."""
        return self.raw_data.get("os_type", "") if self.raw_data else ""

    @property
    def hyper_v_generation(self) -> str:
        """Get the Hyper-V generation (V1, V2)."""
        return self.raw_data.get("hyper_v_generation", "") if self.raw_data else ""

    @property
    def zones(self) -> list[str]:
        """Get the availability zones for this disk."""
        return self.raw_data.get("zones", []) if self.raw_data else []
