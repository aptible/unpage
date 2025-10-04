"""Azure VM Scale Set node implementation."""

from pydantic import AwareDatetime

from unpage.knowledge import HasMetrics
from unpage.models import Observation

from .base import AzureNode


class AzureVmScaleSet(AzureNode, HasMetrics):
    """An Azure VM Scale Set."""

    async def get_identifiers(self) -> list[str | None]:
        identifiers = [
            *await super().get_identifiers(),
        ]

        # Add scale set specific identifiers
        if self.raw_data:
            # Add the SKU name + capacity as an identifier pattern
            sku = self.raw_data.get("sku", {})
            if sku.get("name"):
                identifiers.append(f"vmss:{sku.get('name')}:{sku.get('capacity', 0)}")

        return identifiers

    async def get_reference_identifiers(
        self,
    ) -> list[str | None | tuple[str | None, str]]:
        references = [
            *await super().get_reference_identifiers(),
        ]

        if self.raw_data:
            # Reference to virtual network subnet
            network_profile = self.raw_data.get("virtual_machine_profile", {}).get(
                "network_profile", {}
            )
            for interface_config in network_profile.get("network_interface_configurations", []):
                for ip_config in interface_config.get("ip_configurations", []):
                    subnet = ip_config.get("subnet", {})
                    if subnet.get("id"):
                        references.append((subnet["id"], "in_subnet"))

                    # Load balancer backend pools
                    references.extend(
                        (backend_pool["id"], "in_backend_pool")
                        for backend_pool in ip_config.get("load_balancer_backend_address_pools", [])
                        if backend_pool.get("id")
                    )

                    # Application gateway backend pools
                    references.extend(
                        (backend_pool["id"], "in_app_gateway_pool")
                        for backend_pool in ip_config.get(
                            "application_gateway_backend_address_pools", []
                        )
                        if backend_pool.get("id")
                    )

                # Network security group reference
                nsg = interface_config.get("network_security_group", {})
                if nsg.get("id"):
                    references.append((nsg["id"], "protected_by_nsg"))

            # Storage profile - OS disk
            storage_profile = self.raw_data.get("virtual_machine_profile", {}).get(
                "storage_profile", {}
            )
            os_disk = storage_profile.get("os_disk", {})
            managed_disk = os_disk.get("managed_disk", {})
            if managed_disk.get("storage_account_type"):
                references.append(
                    (f"storage_type:{managed_disk['storage_account_type']}", "uses_storage_type")
                )

        return references

    async def list_available_metrics(self) -> list[str]:
        """List available metrics for Azure VM Scale Set."""
        return [
            "Percentage CPU",
            "Network In Total",
            "Network Out Total",
            "Disk Read Bytes",
            "Disk Write Bytes",
            "Disk Read Operations/Sec",
            "Disk Write Operations/Sec",
            "CPU Credits Remaining",
            "CPU Credits Consumed",
        ]

    async def get_metric(
        self,
        metric_name: str,
        time_range_start: AwareDatetime,
        time_range_end: AwareDatetime,
    ) -> list[Observation] | str:
        """Get specific metric data for this VM Scale Set."""
        # Use appropriate aggregation based on metric type
        aggregation = "Average"
        if "Total" in metric_name or "Bytes" in metric_name:
            aggregation = "Total"

        return await self._get_azure_monitor_metrics(
            metric_names=[metric_name],
            aggregation=aggregation,
            start_time=time_range_start,
            end_time=time_range_end,
            interval="PT5M",  # 5 minute intervals
        )

    @property
    def sku(self) -> dict:
        """Get the SKU information."""
        return self.raw_data.get("sku", {}) if self.raw_data else {}

    @property
    def capacity(self) -> int:
        """Get the current capacity (number of instances)."""
        return self.sku.get("capacity", 0)

    @property
    def provisioning_state(self) -> str:
        """Get the provisioning state."""
        return self.raw_data.get("provisioning_state", "") if self.raw_data else ""

    @property
    def unique_id(self) -> str:
        """Get the unique ID of the scale set."""
        return self.raw_data.get("unique_id", "") if self.raw_data else ""

    @property
    def single_placement_group(self) -> bool:
        """Check if using single placement group."""
        return self.raw_data.get("single_placement_group", True) if self.raw_data else True

    @property
    def overprovision(self) -> bool:
        """Check if overprovisioning is enabled."""
        return self.raw_data.get("overprovision", True) if self.raw_data else True


class AzureVmScaleSetInstance(AzureNode, HasMetrics):
    """An Azure VM Scale Set Instance."""

    async def get_identifiers(self) -> list[str | None]:
        identifiers = [
            *await super().get_identifiers(),
        ]

        # Add instance-specific identifiers
        if self.raw_data:
            # Add instance ID
            instance_id = self.raw_data.get("instance_id")
            if instance_id:
                identifiers.append(f"vmss-instance:{instance_id}")

        return identifiers

    async def get_reference_identifiers(
        self,
    ) -> list[str | None | tuple[str | None, str]]:
        references = [
            *await super().get_reference_identifiers(),
        ]

        if self.raw_data:
            # Reference to parent scale set
            # Parse the ID to get scale set reference
            resource_id = self.raw_data.get("id", "")
            if "/virtualMachineScaleSets/" in resource_id:
                scale_set_id = resource_id.split("/virtualMachines/")[0]
                references.append((scale_set_id, "instance_of"))

            # OS disk
            storage_profile = self.raw_data.get("storage_profile", {})
            os_disk = storage_profile.get("os_disk", {})
            if os_disk.get("managed_disk", {}).get("id"):
                references.append((os_disk["managed_disk"]["id"], "has_os_disk"))

            # Data disks
            references.extend(
                (disk["managed_disk"]["id"], "has_data_disk")
                for disk in storage_profile.get("data_disks", [])
                if disk.get("managed_disk", {}).get("id")
            )

        return references

    async def list_available_metrics(self) -> list[str]:
        """List available metrics for VM Scale Set Instance."""
        return [
            "Percentage CPU",
            "Network In Total",
            "Network Out Total",
            "Disk Read Bytes",
            "Disk Write Bytes",
            "Disk Read Operations/Sec",
            "Disk Write Operations/Sec",
        ]

    async def get_metric(
        self,
        metric_name: str,
        time_range_start: AwareDatetime,
        time_range_end: AwareDatetime,
    ) -> list[Observation] | str:
        """Get specific metric data for this VM Scale Set Instance."""
        aggregation = "Average"
        if "Total" in metric_name or "Bytes" in metric_name:
            aggregation = "Total"

        return await self._get_azure_monitor_metrics(
            metric_names=[metric_name],
            aggregation=aggregation,
            start_time=time_range_start,
            end_time=time_range_end,
            interval="PT5M",
        )

    @property
    def instance_id(self) -> str:
        """Get the instance ID."""
        return self.raw_data.get("instance_id", "") if self.raw_data else ""

    @property
    def sku(self) -> dict:
        """Get the SKU information."""
        return self.raw_data.get("sku", {}) if self.raw_data else {}

    @property
    def latest_model_applied(self) -> bool:
        """Check if latest model is applied."""
        return self.raw_data.get("latest_model_applied", False) if self.raw_data else False

    @property
    def vm_id(self) -> str:
        """Get the VM ID."""
        return self.raw_data.get("vm_id", "") if self.raw_data else ""

    @property
    def instance_state(self) -> str:
        """Get the current instance state."""
        instance_view = self.raw_data.get("instance_view", {}) if self.raw_data else {}
        statuses = instance_view.get("statuses", [])
        for status in statuses:
            if status.get("code", "").startswith("PowerState/"):
                return status.get("display_status", "Unknown")
        return "Unknown"
