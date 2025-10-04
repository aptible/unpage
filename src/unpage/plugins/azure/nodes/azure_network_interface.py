"""Azure Network Interface node implementation."""

from .base import AzureNode


class AzureNetworkInterface(AzureNode):
    """An Azure Network Interface."""

    async def get_identifiers(self) -> list[str | None]:
        identifiers = [
            *await super().get_identifiers(),
        ]

        # Add IP addresses as identifiers
        if self.raw_data:
            ip_configs = self.raw_data.get("ip_configurations", [])
            for ip_config in ip_configs:
                # Private IP
                private_ip = ip_config.get("private_ip_address")
                if private_ip:
                    identifiers.append(private_ip)

                # Public IP (if directly attached)
                public_ip = ip_config.get("public_ip_address", {})
                if public_ip.get("id"):
                    identifiers.append(f"has_public_ip:{public_ip['id']}")

        return identifiers

    async def get_reference_identifiers(
        self,
    ) -> list[str | None | tuple[str | None, str]]:
        references = [
            *await super().get_reference_identifiers(),
        ]

        if self.raw_data:
            # Virtual machine reference
            vm_ref = self.raw_data.get("virtual_machine", {})
            if vm_ref.get("id"):
                references.append((vm_ref["id"], "attached_to_vm"))

            # Network security group reference
            nsg = self.raw_data.get("network_security_group", {})
            if nsg.get("id"):
                references.append((nsg["id"], "protected_by_nsg"))

            # IP configurations
            ip_configs = self.raw_data.get("ip_configurations", [])
            for ip_config in ip_configs:
                # Subnet reference
                subnet = ip_config.get("subnet", {})
                if subnet.get("id"):
                    references.append((subnet["id"], "connected_to_subnet"))

                # Public IP reference
                public_ip = ip_config.get("public_ip_address", {})
                if public_ip.get("id"):
                    references.append((public_ip["id"], "uses_public_ip"))

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

        return references

    @property
    def mac_address(self) -> str:
        """Get the MAC address."""
        return self.raw_data.get("mac_address", "") if self.raw_data else ""

    @property
    def primary(self) -> bool:
        """Check if this is the primary network interface."""
        return self.raw_data.get("primary", False) if self.raw_data else False

    @property
    def enable_accelerated_networking(self) -> bool:
        """Check if accelerated networking is enabled."""
        return self.raw_data.get("enable_accelerated_networking", False) if self.raw_data else False

    @property
    def enable_ip_forwarding(self) -> bool:
        """Check if IP forwarding is enabled."""
        return self.raw_data.get("enable_ip_forwarding", False) if self.raw_data else False

    @property
    def ip_configurations(self) -> list[dict]:
        """Get IP configurations."""
        return self.raw_data.get("ip_configurations", []) if self.raw_data else []

    @property
    def provisioning_state(self) -> str:
        """Get the provisioning state."""
        return self.raw_data.get("provisioning_state", "") if self.raw_data else ""

    @property
    def resource_guid(self) -> str:
        """Get the resource GUID."""
        return self.raw_data.get("resource_guid", "") if self.raw_data else ""

    def get_private_ip_addresses(self) -> list[str]:
        """Get all private IP addresses."""
        ips = []
        for ip_config in self.ip_configurations:
            private_ip = ip_config.get("private_ip_address")
            if private_ip:
                ips.append(private_ip)
        return ips
