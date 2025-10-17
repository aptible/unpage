"""Azure Virtual Network and Subnet node implementations."""

from .base import AzureNode


class AzureVirtualNetwork(AzureNode):
    """An Azure Virtual Network."""

    async def get_identifiers(self) -> list[str | None]:
        identifiers = [
            *await super().get_identifiers(),
        ]

        # Add address spaces as identifiers
        if self.raw_data:
            address_space = self.raw_data.get("address_space", {})
            identifiers.extend(
                f"vnet:{prefix}" for prefix in address_space.get("address_prefixes", []) if prefix
            )
        return identifiers

    async def get_reference_identifiers(
        self,
    ) -> list[str | None | tuple[str | None, str]]:
        references = [
            *await super().get_reference_identifiers(),
        ]

        if self.raw_data:
            # Peerings to other VNets
            for peering in self.raw_data.get("virtual_network_peerings", []):
                remote_vnet = peering.get("remote_virtual_network", {})
                if remote_vnet.get("id"):
                    references.append((remote_vnet["id"], "peered_with"))

            # DDoS protection plan
            ddos_plan = self.raw_data.get("ddos_protection_plan", {})
            if ddos_plan.get("id"):
                references.append((ddos_plan["id"], "protected_by_ddos"))

            # Subnets (these will be separate nodes)
            references.extend(
                (subnet["id"], "has_subnet")
                for subnet in self.raw_data.get("subnets", [])
                if subnet.get("id")
            )

        return references

    @property
    def address_space(self) -> list[str]:
        """Get the address space prefixes."""
        if self.raw_data:
            return self.raw_data.get("address_space", {}).get("address_prefixes", [])
        return []

    @property
    def dns_servers(self) -> list[str]:
        """Get custom DNS servers."""
        if self.raw_data:
            dhcp_options = self.raw_data.get("dhcp_options", {})
            return dhcp_options.get("dns_servers", [])
        return []

    @property
    def subnets(self) -> list[dict]:
        """Get subnet configurations."""
        return self.raw_data.get("subnets", []) if self.raw_data else []

    @property
    def enable_ddos_protection(self) -> bool:
        """Check if DDoS protection is enabled."""
        return self.raw_data.get("enable_ddos_protection", False) if self.raw_data else False

    @property
    def enable_vm_protection(self) -> bool:
        """Check if VM protection is enabled."""
        return self.raw_data.get("enable_vm_protection", False) if self.raw_data else False

    @property
    def provisioning_state(self) -> str:
        """Get the provisioning state."""
        return self.raw_data.get("provisioning_state", "") if self.raw_data else ""


class AzureSubnet(AzureNode):
    """An Azure Subnet."""

    async def get_identifiers(self) -> list[str | None]:
        identifiers = [
            *await super().get_identifiers(),
        ]

        # Add address prefix as identifier
        if self.raw_data:
            address_prefix = self.raw_data.get("address_prefix")
            if address_prefix:
                identifiers.append(f"subnet:{address_prefix}")

            # Add address prefixes (for subnets with multiple ranges)
            identifiers.extend(
                f"subnet:{prefix}" for prefix in self.raw_data.get("address_prefixes", []) if prefix
            )

        return identifiers

    async def get_reference_identifiers(
        self,
    ) -> list[str | None | tuple[str | None, str]]:
        references = [
            *await super().get_reference_identifiers(),
        ]

        if self.raw_data:
            # Parent VNet reference
            resource_id = self.raw_data.get("id", "")
            if "/virtualNetworks/" in resource_id and "/subnets/" in resource_id:
                vnet_id = resource_id.split("/subnets/")[0]
                references.append((vnet_id, "subnet_of"))

            # Network security group
            nsg = self.raw_data.get("network_security_group", {})
            if nsg.get("id"):
                references.append((nsg["id"], "protected_by_nsg"))

            # Route table
            route_table = self.raw_data.get("route_table", {})
            if route_table.get("id"):
                references.append((route_table["id"], "uses_route_table"))

            # NAT gateway
            nat_gateway = self.raw_data.get("nat_gateway", {})
            if nat_gateway.get("id"):
                references.append((nat_gateway["id"], "uses_nat_gateway"))

            # Service endpoints
            for endpoint in self.raw_data.get("service_endpoints", []):
                service = endpoint.get("service")
                if service:
                    references.append((f"service_endpoint:{service}", "has_service_endpoint"))

        return references

    @property
    def address_prefix(self) -> str:
        """Get the address prefix."""
        return self.raw_data.get("address_prefix", "") if self.raw_data else ""

    @property
    def address_prefixes(self) -> list[str]:
        """Get multiple address prefixes."""
        return self.raw_data.get("address_prefixes", []) if self.raw_data else []

    @property
    def private_endpoint_network_policies(self) -> str:
        """Get private endpoint network policies setting."""
        return (
            self.raw_data.get("private_endpoint_network_policies", "Enabled")
            if self.raw_data
            else "Enabled"
        )

    @property
    def private_link_service_network_policies(self) -> str:
        """Get private link service network policies setting."""
        return (
            self.raw_data.get("private_link_service_network_policies", "Enabled")
            if self.raw_data
            else "Enabled"
        )

    @property
    def service_endpoints(self) -> list[dict]:
        """Get service endpoints."""
        return self.raw_data.get("service_endpoints", []) if self.raw_data else []

    @property
    def delegations(self) -> list[dict]:
        """Get subnet delegations."""
        return self.raw_data.get("delegations", []) if self.raw_data else []

    @property
    def provisioning_state(self) -> str:
        """Get the provisioning state."""
        return self.raw_data.get("provisioning_state", "") if self.raw_data else ""
