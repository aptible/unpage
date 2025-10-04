"""Azure Public IP Address node implementation."""

from .base import AzureNode


class AzurePublicIpAddress(AzureNode):
    """An Azure Public IP Address."""

    async def get_identifiers(self) -> list[str | None]:
        identifiers = [
            *await super().get_identifiers(),
        ]

        # Add the actual IP address as an identifier
        if self.raw_data:
            ip_address = self.raw_data.get("ip_address")
            if ip_address:
                identifiers.append(ip_address)

            # Add DNS name if configured
            dns_settings = self.raw_data.get("dns_settings", {})
            fqdn = dns_settings.get("fqdn")
            if fqdn:
                identifiers.append(fqdn)

            domain_label = dns_settings.get("domain_name_label")
            if domain_label:
                identifiers.append(domain_label)

        return identifiers

    async def get_reference_identifiers(
        self,
    ) -> list[str | None | tuple[str | None, str]]:
        references = [
            *await super().get_reference_identifiers(),
        ]

        if self.raw_data:
            # Reference to associated resource (if any)
            ip_config = self.raw_data.get("ip_configuration", {})
            if ip_config.get("id"):
                # Determine the type of resource
                config_id = ip_config["id"]
                if "/loadBalancers/" in config_id:
                    references.append((config_id, "assigned_to_lb"))
                elif "/networkInterfaces/" in config_id:
                    references.append((config_id, "assigned_to_nic"))
                elif "/applicationGateways/" in config_id:
                    references.append((config_id, "assigned_to_app_gateway"))
                else:
                    references.append((config_id, "assigned_to"))

            # NAT gateway reference
            nat_gateway = self.raw_data.get("nat_gateway", {})
            if nat_gateway.get("id"):
                references.append((nat_gateway["id"], "used_by_nat_gateway"))

            # Public IP prefix reference
            prefix = self.raw_data.get("public_ip_prefix", {})
            if prefix.get("id"):
                references.append((prefix["id"], "from_ip_prefix"))

        return references

    @property
    def ip_address(self) -> str:
        """Get the actual IP address."""
        return self.raw_data.get("ip_address", "") if self.raw_data else ""

    @property
    def allocation_method(self) -> str:
        """Get the allocation method (Static or Dynamic)."""
        return self.raw_data.get("public_ip_allocation_method", "") if self.raw_data else ""

    @property
    def ip_version(self) -> str:
        """Get the IP version (IPv4 or IPv6)."""
        return self.raw_data.get("public_ip_address_version", "IPv4") if self.raw_data else "IPv4"

    @property
    def sku_name(self) -> str:
        """Get the SKU name (Basic or Standard)."""
        sku = self.raw_data.get("sku", {}) if self.raw_data else {}
        return sku.get("name", "")

    @property
    def sku_tier(self) -> str:
        """Get the SKU tier."""
        sku = self.raw_data.get("sku", {}) if self.raw_data else {}
        return sku.get("tier", "")

    @property
    def dns_settings(self) -> dict:
        """Get DNS settings."""
        return self.raw_data.get("dns_settings", {}) if self.raw_data else {}

    @property
    def fqdn(self) -> str:
        """Get the fully qualified domain name."""
        return self.dns_settings.get("fqdn", "")

    @property
    def provisioning_state(self) -> str:
        """Get the provisioning state."""
        return self.raw_data.get("provisioning_state", "") if self.raw_data else ""

    @property
    def idle_timeout_in_minutes(self) -> int:
        """Get the idle timeout in minutes."""
        return self.raw_data.get("idle_timeout_in_minutes", 4) if self.raw_data else 4

    @property
    def zones(self) -> list[str]:
        """Get availability zones."""
        return self.raw_data.get("zones", []) if self.raw_data else []
