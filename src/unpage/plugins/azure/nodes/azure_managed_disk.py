"""Azure Managed Disk node implementation."""

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

        # Add disk-specific identifiers
        if self.raw_data:
            # Add unique disk ID
            unique_id = self.raw_data.get("unique_id")
            if unique_id:
                identifiers.append(f"disk:{unique_id}")

        return identifiers

    async def get_reference_identifiers(
        self,
    ) -> list[str | None | tuple[str | None, str]]:
        references = [
            *await super().get_reference_identifiers(),
        ]

        if self.raw_data:
            # Disk encryption set reference
            encryption = self.raw_data.get("encryption", {})
            disk_encryption_set_id = encryption.get("disk_encryption_set_id")
            if disk_encryption_set_id:
                references.append((disk_encryption_set_id, "encrypted_by"))

            # Source resource (for disks created from snapshots/images)
            creation_data = self.raw_data.get("creation_data", {})
            source_resource_id = creation_data.get("source_resource_id")
            if source_resource_id:
                references.append((source_resource_id, "created_from"))

            # Storage account type
            sku = self.raw_data.get("sku", {})
            storage_type = sku.get("name")
            if storage_type:
                references.append((f"storage_type:{storage_type}", "uses_storage_type"))

        return references

    async def list_available_metrics(self) -> list[str]:
        """List available metrics for Managed Disk."""
        return [
            "Composite Disk Read Bytes/sec",
            "Composite Disk Write Bytes/sec",
            "Composite Disk Read Operations/sec",
            "Composite Disk Write Operations/sec",
            "Disk On-demand Burst Operations",
            "Used Disk IOPS Consumed Percentage",
            "Used Disk Bandwidth Consumed Percentage",
        ]

    async def get_metric(
        self,
        metric_name: str,
        time_range_start: AwareDatetime,
        time_range_end: AwareDatetime,
    ) -> list[Observation] | str:
        """Get specific metric data for this Managed Disk."""
        aggregation = "Average"
        if "Operations" in metric_name or "Bytes" in metric_name:
            aggregation = "Total"

        return await self._get_azure_monitor_metrics(
            metric_names=[metric_name],
            aggregation=aggregation,
            start_time=time_range_start,
            end_time=time_range_end,
            interval="PT5M",
        )

    @property
    def disk_size_gb(self) -> int:
        """Get the disk size in GB."""
        return self.raw_data.get("disk_size_gb", 0) if self.raw_data else 0

    @property
    def disk_state(self) -> str:
        """Get the disk state."""
        return self.raw_data.get("disk_state", "") if self.raw_data else ""

    @property
    def provisioning_state(self) -> str:
        """Get the provisioning state."""
        return self.raw_data.get("provisioning_state", "") if self.raw_data else ""

    @property
    def sku_name(self) -> str:
        """Get the storage SKU name."""
        sku = self.raw_data.get("sku", {}) if self.raw_data else {}
        return sku.get("name", "")

    @property
    def sku_tier(self) -> str:
        """Get the storage SKU tier."""
        sku = self.raw_data.get("sku", {}) if self.raw_data else {}
        return sku.get("tier", "")

    @property
    def creation_data(self) -> dict:
        """Get the creation data."""
        return self.raw_data.get("creation_data", {}) if self.raw_data else {}

    @property
    def os_type(self) -> str:
        """Get the OS type (for OS disks)."""
        return self.raw_data.get("os_type", "") if self.raw_data else ""

    @property
    def hyper_v_generation(self) -> str:
        """Get the Hyper-V generation."""
        return self.raw_data.get("hyper_v_generation", "") if self.raw_data else ""

    @property
    def network_access_policy(self) -> str:
        """Get the network access policy."""
        return self.raw_data.get("network_access_policy", "") if self.raw_data else ""

    @property
    def public_network_access(self) -> str:
        """Get the public network access setting."""
        return self.raw_data.get("public_network_access", "") if self.raw_data else ""

    @property
    def unique_id(self) -> str:
        """Get the unique ID of the disk."""
        return self.raw_data.get("unique_id", "") if self.raw_data else ""

    @property
    def zones(self) -> list[str]:
        """Get the availability zones."""
        return self.raw_data.get("zones", []) if self.raw_data else []
