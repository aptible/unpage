"""Azure Network Security Group node implementation."""

from .base import AzureNode


class AzureNetworkSecurityGroup(AzureNode):
    """An Azure Network Security Group."""

    async def get_identifiers(self) -> list[str | None]:
        identifiers = [
            *await super().get_identifiers(),
        ]

        # NSGs are primarily identified by their resource ID and name
        # No additional identifiers needed

        return identifiers

    async def get_reference_identifiers(
        self,
    ) -> list[str | None | tuple[str | None, str]]:
        references = [
            *await super().get_reference_identifiers(),
        ]

        if self.raw_data:
            # Subnets using this NSG
            references.extend(
                (subnet["id"], "protects_subnet")
                for subnet in self.raw_data.get("subnets", [])
                if subnet.get("id")
            )

            # Network interfaces using this NSG
            references.extend(
                (nic["id"], "protects_interface")
                for nic in self.raw_data.get("network_interfaces", [])
                if nic.get("id")
            )

            # Flow logs (if configured)
            references.extend(
                (flow_log["id"], "has_flow_log")
                for flow_log in self.raw_data.get("flow_logs", [])
                if flow_log.get("id")
            )

        return references

    @property
    def security_rules(self) -> list[dict]:
        """Get security rules."""
        return self.raw_data.get("security_rules", []) if self.raw_data else []

    @property
    def default_security_rules(self) -> list[dict]:
        """Get default security rules."""
        return self.raw_data.get("default_security_rules", []) if self.raw_data else []

    @property
    def subnets(self) -> list[dict]:
        """Get associated subnets."""
        return self.raw_data.get("subnets", []) if self.raw_data else []

    @property
    def network_interfaces(self) -> list[dict]:
        """Get associated network interfaces."""
        return self.raw_data.get("network_interfaces", []) if self.raw_data else []

    @property
    def provisioning_state(self) -> str:
        """Get the provisioning state."""
        return self.raw_data.get("provisioning_state", "") if self.raw_data else ""

    @property
    def resource_guid(self) -> str:
        """Get the resource GUID."""
        return self.raw_data.get("resource_guid", "") if self.raw_data else ""

    def get_inbound_rules(self) -> list[dict]:
        """Get all inbound security rules (custom + default)."""
        rules = []
        rules.extend(
            rule
            for rule in self.security_rules + self.default_security_rules
            if rule.get("direction") == "Inbound"
        )
        return sorted(rules, key=lambda x: x.get("priority", 9999))

    def get_outbound_rules(self) -> list[dict]:
        """Get all outbound security rules (custom + default)."""
        rules = []
        rules.extend(
            rule
            for rule in self.security_rules + self.default_security_rules
            if rule.get("direction") == "Outbound"
        )
        return sorted(rules, key=lambda x: x.get("priority", 9999))

    def has_open_port(self, port: int) -> bool:
        """Check if a specific port is open to the internet."""
        for rule in self.get_inbound_rules():
            if rule.get("access") != "Allow":
                continue

            # Check source
            source = rule.get("source_address_prefix", "")
            if source not in ["*", "Internet", "0.0.0.0/0"]:
                continue

            # Check port ranges
            dest_port = rule.get("destination_port_range")
            if dest_port:
                if dest_port == "*":
                    return True
                if "-" in dest_port:
                    start, end = dest_port.split("-")
                    if int(start) <= port <= int(end):
                        return True
                elif str(port) == dest_port:
                    return True

            # Check multiple port ranges
            for port_range in rule.get("destination_port_ranges", []):
                if port_range == "*":
                    return True
                if "-" in port_range:
                    start, end = port_range.split("-")
                    if int(start) <= port <= int(end):
                        return True
                elif str(port) == port_range:
                    return True

        return False
