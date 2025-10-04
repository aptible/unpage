from pydantic import AwareDatetime

from unpage.knowledge import HasMetrics
from unpage.models import Observation

from .base import AzureNode


class AzureVmInstance(AzureNode, HasMetrics):
    """An Azure Virtual Machine instance."""

    async def get_identifiers(self) -> list[str | None]:
        identifiers = [
            *await super().get_identifiers(),
        ]

        # Add VM-specific identifiers
        if self.raw_data:
            # Add private IP addresses
            if self.raw_data.get("network_profile"):
                network_interfaces = self.raw_data["network_profile"].get("network_interfaces", [])
                # The network interface ID can be used to get IP addresses
                # In a real implementation, you might want to fetch the actual IP addresses
                identifiers.extend([ni.get("id") for ni in network_interfaces if ni.get("id")])

            # Add computer name if available (from OS profile)
            if self.raw_data.get("os_profile"):
                computer_name = self.raw_data["os_profile"].get("computer_name")
                if computer_name:
                    identifiers.append(computer_name)

            # Add VM size as a form of identifier
            if self.raw_data.get("hardware_profile"):
                vm_size = self.raw_data["hardware_profile"].get("vm_size")
                if vm_size:
                    identifiers.append(f"{self.resource_name}-{vm_size}")

        return identifiers

    async def get_reference_identifiers(
        self,
    ) -> list[str | None | tuple[str | None, str]]:
        references = [
            *await super().get_reference_identifiers(),
        ]

        if self.raw_data:
            # Add network interface references
            if self.raw_data.get("network_profile"):
                network_interfaces = self.raw_data["network_profile"].get("network_interfaces", [])
                for ni in network_interfaces:
                    ni_id = ni.get("id")
                    if ni_id:
                        references.append((ni_id, "has_network_interface"))

            # Add managed disk references
            if self.raw_data.get("storage_profile"):
                # OS disk
                os_disk = self.raw_data["storage_profile"].get("os_disk", {})
                if os_disk.get("managed_disk"):
                    disk_id = os_disk["managed_disk"].get("id")
                    if disk_id:
                        references.append((disk_id, "has_os_disk"))

                # Data disks
                data_disks = self.raw_data["storage_profile"].get("data_disks", [])
                for data_disk in data_disks:
                    if data_disk.get("managed_disk"):
                        disk_id = data_disk["managed_disk"].get("id")
                        if disk_id:
                            references.append((disk_id, "has_data_disk"))

        return references

    async def list_available_metrics(self) -> list[str]:
        """List available metrics for Azure VMs."""
        return [
            "Percentage CPU",
            "Network In Total",
            "Network Out Total",
            "Disk Read Bytes",
            "Disk Write Bytes",
            "Disk Read Operations/Sec",
            "Disk Write Operations/Sec",
            "CPU Credits Remaining",  # For B-series VMs
            "CPU Credits Consumed",  # For B-series VMs
            "Inbound Flows",
            "Outbound Flows",
            "Available Memory Bytes",  # Requires Azure Monitor Agent
        ]

    async def get_metric(
        self,
        metric_name: str,
        time_range_start: AwareDatetime,
        time_range_end: AwareDatetime,
    ) -> list[Observation] | str:
        """Get specific metric data for this Azure VM."""
        return await self._get_azure_monitor_metrics(
            metric_names=[metric_name],
            aggregation="Average",
            start_time=time_range_start,
            end_time=time_range_end,
            interval="PT5M",  # 5 minute intervals
        )

    @property
    def vm_size(self) -> str:
        """Get the VM size/SKU."""
        if self.raw_data and "hardware_profile" in self.raw_data:
            return self.raw_data["hardware_profile"].get("vm_size", "")
        return ""

    @property
    def power_state(self) -> str:
        """Get the current power state (if available in raw data)."""
        # Note: This would typically require a separate API call to get instance view
        # The static VM data doesn't include current power state
        return "Unknown"

    @property
    def operating_system(self) -> str:
        """Get the operating system type."""
        if self.raw_data and "storage_profile" in self.raw_data:
            os_disk = self.raw_data["storage_profile"].get("os_disk", {})
            return os_disk.get("os_type", "Unknown")
        return "Unknown"

    @property
    def vm_id(self) -> str:
        """Get the VM ID (same as resource_id for Azure VMs)."""
        return self.resource_id
