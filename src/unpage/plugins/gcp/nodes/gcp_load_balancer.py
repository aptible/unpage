"""Google Cloud Load Balancer nodes."""

from typing import TYPE_CHECKING

from unpage.knowledge import HasMetrics
from unpage.models import Observation
from unpage.plugins.gcp.nodes.base import GcpNode

if TYPE_CHECKING:
    from pydantic import AwareDatetime


class GcpLoadBalancer(GcpNode, HasMetrics):
    """A Google Cloud Load Balancer (HTTP/HTTPS)."""

    async def get_identifiers(self) -> list[str | None]:
        """Get unique identifiers for this load balancer."""
        identifiers = await super().get_identifiers()

        # Add load balancer-specific identifiers
        identifiers.extend(
            [
                self.raw_data.get("id"),  # Numeric ID
                self.raw_data.get("name"),  # Load balancer name
                self.raw_data.get("selfLink"),  # Full resource URL
            ]
        )

        # Add IP address if available
        ip_address = self.raw_data.get("IPAddress")
        if ip_address:
            identifiers.append(ip_address)

        return identifiers

    async def get_reference_identifiers(self) -> list[str | None | tuple[str | None, str]]:
        """Get identifiers that reference other resources."""
        refs = await super().get_reference_identifiers()

        # Add backend service references
        for url_map in self.raw_data.get("urlMaps", []):
            if url_map:
                url_map_id = url_map.split("/")[-1]
                refs.append((url_map_id, "uses_url_map"))

        # Add target proxy references
        for target_proxy in self.raw_data.get("targetProxies", []):
            if target_proxy:
                proxy_id = target_proxy.split("/")[-1]
                refs.append((proxy_id, "uses_target_proxy"))

        return refs

    async def list_available_metrics(self) -> list[str]:
        """List available Cloud Monitoring metrics for this load balancer."""
        return [
            "loadbalancing.googleapis.com/https/request_count",
            "loadbalancing.googleapis.com/https/request_bytes_count",
            "loadbalancing.googleapis.com/https/response_bytes_count",
            "loadbalancing.googleapis.com/https/total_latencies",
            "loadbalancing.googleapis.com/https/backend_latencies",
            "loadbalancing.googleapis.com/https/frontend_tcp_rtt",
            "loadbalancing.googleapis.com/https/backend_request_count",
            "loadbalancing.googleapis.com/https/backend_request_bytes_count",
            "loadbalancing.googleapis.com/https/backend_response_bytes_count",
        ]

    async def get_metric(
        self,
        metric_name: str,
        time_range_start: "AwareDatetime",
        time_range_end: "AwareDatetime",
    ) -> list[Observation] | str:
        """Get metrics from Cloud Monitoring for this load balancer."""

        # Build resource labels
        resource_labels = {
            "url_map_name": self.raw_data.get("name", ""),
            "project_id": self.project_id,
            "forwarding_rule_name": self.raw_data.get("name", ""),
            "target_proxy_name": self.raw_data.get("name", ""),
        }

        return await self._get_cloud_monitoring_metrics(
            metric_type=metric_name,
            resource_type="https_lb_rule",
            resource_labels=resource_labels,
            start_time=time_range_start,
            end_time=time_range_end,
        )

    @property
    def display_name(self) -> str:
        """Get a human-readable display name for this load balancer."""
        return self.raw_data.get("name", "Unknown Load Balancer")

    @property
    def load_balancer_type(self) -> str:
        """Get the type of load balancer."""
        return self.raw_data.get("kind", "").replace("compute#", "")


class GcpBackendService(GcpNode, HasMetrics):
    """A Google Cloud Backend Service."""

    async def get_identifiers(self) -> list[str | None]:
        """Get unique identifiers for this backend service."""
        identifiers = await super().get_identifiers()

        # Add backend service-specific identifiers
        identifiers.extend(
            [
                self.raw_data.get("id"),  # Numeric ID
                self.raw_data.get("name"),  # Backend service name
                self.raw_data.get("selfLink"),  # Full resource URL
            ]
        )

        return identifiers

    async def get_reference_identifiers(self) -> list[str | None | tuple[str | None, str]]:
        """Get identifiers that reference other resources."""
        refs = await super().get_reference_identifiers()

        # Add backend instance group references
        for backend in self.raw_data.get("backends", []):
            group = backend.get("group")
            if group:
                # Extract instance group name from URL
                group_id = group.split("/")[-1]
                refs.append((group_id, "uses_instance_group"))

        # Add health check references
        for health_check in self.raw_data.get("healthChecks", []):
            if health_check:
                check_id = health_check.split("/")[-1]
                refs.append((check_id, "uses_health_check"))

        return refs

    async def list_available_metrics(self) -> list[str]:
        """List available Cloud Monitoring metrics for this backend service."""
        return [
            "loadbalancing.googleapis.com/https/backend_request_count",
            "loadbalancing.googleapis.com/https/backend_request_bytes_count",
            "loadbalancing.googleapis.com/https/backend_response_bytes_count",
            "loadbalancing.googleapis.com/https/backend_latencies",
        ]

    async def get_metric(
        self,
        metric_name: str,
        time_range_start: "AwareDatetime",
        time_range_end: "AwareDatetime",
    ) -> list[Observation] | str:
        """Get metrics from Cloud Monitoring for this backend service."""

        resource_labels = {
            "backend_service_name": self.raw_data.get("name", ""),
            "project_id": self.project_id,
        }

        return await self._get_cloud_monitoring_metrics(
            metric_type=metric_name,
            resource_type="https_backend_service",
            resource_labels=resource_labels,
            start_time=time_range_start,
            end_time=time_range_end,
        )

    @property
    def display_name(self) -> str:
        """Get a human-readable display name for this backend service."""
        return self.raw_data.get("name", "Unknown Backend Service")

    @property
    def protocol(self) -> str:
        """Get the protocol used by this backend service."""
        return self.raw_data.get("protocol", "UNKNOWN")

    @property
    def load_balancing_scheme(self) -> str:
        """Get the load balancing scheme."""
        return self.raw_data.get("loadBalancingScheme", "EXTERNAL")

    @property
    def session_affinity(self) -> str:
        """Get the session affinity setting."""
        return self.raw_data.get("sessionAffinity", "NONE")


class GcpTargetPool(GcpNode):
    """A Google Cloud Target Pool (for Network Load Balancers)."""

    async def get_identifiers(self) -> list[str | None]:
        """Get unique identifiers for this target pool."""
        identifiers = await super().get_identifiers()

        # Add target pool-specific identifiers
        identifiers.extend(
            [
                self.raw_data.get("id"),  # Numeric ID
                self.raw_data.get("name"),  # Target pool name
                self.raw_data.get("selfLink"),  # Full resource URL
            ]
        )

        return identifiers

    async def get_reference_identifiers(self) -> list[str | None | tuple[str | None, str]]:
        """Get identifiers that reference other resources."""
        refs = await super().get_reference_identifiers()

        # Add instance references
        for instance in self.raw_data.get("instances", []):
            if instance:
                # Extract instance name from URL
                instance_id = instance.split("/")[-1]
                refs.append((instance_id, "contains_instance"))

        # Add health check references
        for health_check in self.raw_data.get("healthChecks", []):
            if health_check:
                check_id = health_check.split("/")[-1]
                refs.append((check_id, "uses_health_check"))

        return refs

    @property
    def display_name(self) -> str:
        """Get a human-readable display name for this target pool."""
        return self.raw_data.get("name", "Unknown Target Pool")

    @property
    def session_affinity(self) -> str:
        """Get the session affinity setting."""
        return self.raw_data.get("sessionAffinity", "NONE")

    @property
    def region(self) -> str:
        """Get the region of this target pool."""
        region_url = self.raw_data.get("region", "")
        return region_url.split("/")[-1] if region_url else "unknown"
