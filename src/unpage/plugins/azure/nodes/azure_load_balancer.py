from pydantic import AwareDatetime

from unpage.knowledge import HasMetrics
from unpage.models import Observation

from .base import AzureNode


class AzureLoadBalancer(AzureNode, HasMetrics):
    """An Azure Load Balancer."""

    async def get_identifiers(self) -> list[str | None]:
        identifiers = [
            *await super().get_identifiers(),
        ]

        if self.raw_data:
            # Add frontend IP configurations as identifiers
            frontend_ip_configs = self.raw_data.get("frontend_ip_configurations", [])
            for frontend_config in frontend_ip_configs:
                # Private IP
                private_ip = frontend_config.get("private_ip_address")
                if private_ip:
                    identifiers.append(private_ip)

                # Public IP reference (would need separate call to resolve)
                public_ip_ref = frontend_config.get("public_ip_address", {})
                if public_ip_ref and "id" in public_ip_ref:
                    identifiers.append(public_ip_ref["id"])

        return identifiers

    async def get_reference_identifiers(
        self,
    ) -> list[str | None | tuple[str | None, str]]:
        references = [
            *await super().get_reference_identifiers(),
        ]

        if self.raw_data:
            # Add backend address pool references
            backend_pools = self.raw_data.get("backend_address_pools", [])
            for pool in backend_pools:
                pool_id = pool.get("id")
                if pool_id:
                    references.append((pool_id, "has_backend_pool"))

            # Add public IP references
            frontend_ip_configs = self.raw_data.get("frontend_ip_configurations", [])
            for frontend_config in frontend_ip_configs:
                public_ip_ref = frontend_config.get("public_ip_address", {})
                if public_ip_ref and "id" in public_ip_ref:
                    references.append((public_ip_ref["id"], "uses_public_ip"))

            # Add subnet references
            for frontend_config in frontend_ip_configs:
                subnet_ref = frontend_config.get("subnet", {})
                if subnet_ref and "id" in subnet_ref:
                    references.append((subnet_ref["id"], "in_subnet"))

        return references

    async def list_available_metrics(self) -> list[str]:
        """List available metrics for Azure Load Balancer."""
        return [
            "VipAvailability",
            "DipAvailability",
            "ByteCount",
            "PacketCount",
            "SYNCount",
            "SnatConnectionCount",
            "AllocatedSnatPorts",
            "UsedSnatPorts",
        ]

    async def get_metric(
        self,
        metric_name: str,
        time_range_start: AwareDatetime,
        time_range_end: AwareDatetime,
    ) -> list[Observation] | str:
        """Get specific metric data for this Azure Load Balancer."""
        # Use appropriate aggregation based on metric type
        aggregation = "Average"
        if metric_name in ["ByteCount", "PacketCount", "SYNCount"]:
            aggregation = "Total"

        return await self._get_azure_monitor_metrics(
            metric_names=[metric_name],
            aggregation=aggregation,
            start_time=time_range_start,
            end_time=time_range_end,
            interval="PT5M",  # 5 minute intervals
        )

    @property
    def sku_name(self) -> str:
        """Get the Load Balancer SKU (Basic, Standard)."""
        sku = self.raw_data.get("sku", {}) if self.raw_data else {}
        return sku.get("name", "")

    @property
    def sku_tier(self) -> str:
        """Get the Load Balancer SKU tier."""
        sku = self.raw_data.get("sku", {}) if self.raw_data else {}
        return sku.get("tier", "")

    @property
    def provisioning_state(self) -> str:
        """Get the provisioning state."""
        return self.raw_data.get("provisioning_state", "") if self.raw_data else ""

    @property
    def frontend_ip_configurations(self) -> list[dict]:
        """Get frontend IP configurations."""
        return self.raw_data.get("frontend_ip_configurations", []) if self.raw_data else []

    @property
    def backend_address_pools(self) -> list[dict]:
        """Get backend address pools."""
        return self.raw_data.get("backend_address_pools", []) if self.raw_data else []

    @property
    def load_balancing_rules(self) -> list[dict]:
        """Get load balancing rules."""
        return self.raw_data.get("load_balancing_rules", []) if self.raw_data else []

    @property
    def probes(self) -> list[dict]:
        """Get health probes."""
        return self.raw_data.get("probes", []) if self.raw_data else []

    @property
    def inbound_nat_rules(self) -> list[dict]:
        """Get inbound NAT rules."""
        return self.raw_data.get("inbound_nat_rules", []) if self.raw_data else []
