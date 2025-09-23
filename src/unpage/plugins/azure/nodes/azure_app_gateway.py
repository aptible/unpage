from pydantic import AwareDatetime

from unpage.knowledge import HasMetrics
from unpage.models import Observation

from .base import AzureNode


class AzureAppGateway(AzureNode, HasMetrics):
    """An Azure Application Gateway."""

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

                # Public IP reference
                public_ip_ref = frontend_config.get("public_ip_address", {})
                if public_ip_ref and "id" in public_ip_ref:
                    identifiers.append(public_ip_ref["id"])

            # Add FQDN if available
            fqdn = self.raw_data.get("fqdn")
            if fqdn:
                identifiers.append(fqdn)

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
            gateway_ip_configs = self.raw_data.get("gateway_ip_configurations", [])
            for gateway_config in gateway_ip_configs:
                subnet_ref = gateway_config.get("subnet", {})
                if subnet_ref and "id" in subnet_ref:
                    references.append((subnet_ref["id"], "in_subnet"))

            # Add SSL certificate references
            ssl_certificates = self.raw_data.get("ssl_certificates", [])
            for cert in ssl_certificates:
                cert_id = cert.get("id")
                if cert_id:
                    references.append((cert_id, "uses_ssl_certificate"))

        return references

    async def list_available_metrics(self) -> list[str]:
        """List available metrics for Azure Application Gateway."""
        return [
            "Throughput",
            "UnhealthyHostCount",
            "HealthyHostCount",
            "TotalRequests",
            "AvgRequestCountPerHealthyHost",
            "FailedRequests",
            "ResponseStatus",
            "CurrentConnections",
            "NewConnectionsPerSecond",
            "CpuUtilization",
            "CapacityUnits",
            "FixedBillableCapacityUnits",
            "EstimatedBilledCapacityUnits",
            "ComputeUnits",
            "BackendConnectTime",
            "BackendFirstByteResponseTime",
            "BackendLastByteResponseTime",
            "MatchedCount",
            "BlockedCount",
            "BlockedReqCount",
        ]

    async def get_metric(
        self,
        metric_name: str,
        time_range_start: AwareDatetime,
        time_range_end: AwareDatetime,
    ) -> list[Observation] | str:
        """Get specific metric data for this Azure Application Gateway."""
        # Use appropriate aggregation based on metric type
        aggregation = "Average"
        if metric_name in ["TotalRequests", "FailedRequests", "MatchedCount", "BlockedCount"]:
            aggregation = "Total"
        elif metric_name in ["UnhealthyHostCount", "HealthyHostCount"]:
            aggregation = "Average"

        return await self._get_azure_monitor_metrics(
            metric_names=[metric_name],
            aggregation=aggregation,
            start_time=time_range_start,
            end_time=time_range_end,
            interval="PT5M",  # 5 minute intervals
        )

    @property
    def sku_name(self) -> str:
        """Get the Application Gateway SKU (Standard, Standard_v2, WAF, WAF_v2)."""
        sku = self.raw_data.get("sku", {}) if self.raw_data else {}
        return sku.get("name", "")

    @property
    def sku_tier(self) -> str:
        """Get the Application Gateway SKU tier."""
        sku = self.raw_data.get("sku", {}) if self.raw_data else {}
        return sku.get("tier", "")

    @property
    def sku_capacity(self) -> int | None:
        """Get the Application Gateway SKU capacity."""
        sku = self.raw_data.get("sku", {}) if self.raw_data else {}
        capacity = sku.get("capacity")
        return int(capacity) if capacity is not None else None

    @property
    def provisioning_state(self) -> str:
        """Get the provisioning state."""
        return self.raw_data.get("provisioning_state", "") if self.raw_data else ""

    @property
    def operational_state(self) -> str:
        """Get the operational state."""
        return self.raw_data.get("operational_state", "") if self.raw_data else ""

    @property
    def gateway_ip_configurations(self) -> list[dict]:
        """Get gateway IP configurations."""
        return self.raw_data.get("gateway_ip_configurations", []) if self.raw_data else []

    @property
    def frontend_ip_configurations(self) -> list[dict]:
        """Get frontend IP configurations."""
        return self.raw_data.get("frontend_ip_configurations", []) if self.raw_data else []

    @property
    def frontend_ports(self) -> list[dict]:
        """Get frontend ports."""
        return self.raw_data.get("frontend_ports", []) if self.raw_data else []

    @property
    def backend_address_pools(self) -> list[dict]:
        """Get backend address pools."""
        return self.raw_data.get("backend_address_pools", []) if self.raw_data else []

    @property
    def backend_http_settings_collection(self) -> list[dict]:
        """Get backend HTTP settings."""
        return self.raw_data.get("backend_http_settings_collection", []) if self.raw_data else []

    @property
    def http_listeners(self) -> list[dict]:
        """Get HTTP listeners."""
        return self.raw_data.get("http_listeners", []) if self.raw_data else []

    @property
    def request_routing_rules(self) -> list[dict]:
        """Get request routing rules."""
        return self.raw_data.get("request_routing_rules", []) if self.raw_data else []

    @property
    def probes(self) -> list[dict]:
        """Get health probes."""
        return self.raw_data.get("probes", []) if self.raw_data else []

    @property
    def ssl_certificates(self) -> list[dict]:
        """Get SSL certificates."""
        return self.raw_data.get("ssl_certificates", []) if self.raw_data else []

    @property
    def url_path_maps(self) -> list[dict]:
        """Get URL path maps."""
        return self.raw_data.get("url_path_maps", []) if self.raw_data else []

    @property
    def web_application_firewall_configuration(self) -> dict:
        """Get WAF configuration."""
        return (
            self.raw_data.get("web_application_firewall_configuration", {}) if self.raw_data else {}
        )

    @property
    def is_waf_enabled(self) -> bool:
        """Check if WAF is enabled."""
        waf_config = self.web_application_firewall_configuration
        return waf_config.get("enabled", False)

    @property
    def waf_mode(self) -> str:
        """Get WAF mode (Detection, Prevention)."""
        waf_config = self.web_application_firewall_configuration
        return waf_config.get("firewall_mode", "")
