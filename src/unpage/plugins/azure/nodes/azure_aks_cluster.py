"""Azure AKS Managed Cluster node implementation."""

from pydantic import AwareDatetime

from unpage.knowledge import HasMetrics
from unpage.models import Observation

from .base import AzureNode


class AzureAksCluster(AzureNode, HasMetrics):
    """An Azure Kubernetes Service (AKS) Managed Cluster."""

    async def get_identifiers(self) -> list[str | None]:
        identifiers = [
            *await super().get_identifiers(),
        ]

        # Add cluster-specific identifiers
        if self.raw_data:
            # Add FQDN as identifier
            fqdn = self.raw_data.get("fqdn")
            if fqdn:
                identifiers.append(fqdn)

            # Add DNS prefix
            dns_prefix = self.raw_data.get("dns_prefix")
            if dns_prefix:
                identifiers.append(f"aks:{dns_prefix}")

        return identifiers

    async def get_reference_identifiers(
        self,
    ) -> list[str | None | tuple[str | None, str]]:
        references = [
            *await super().get_reference_identifiers(),
        ]

        if self.raw_data:
            # Node resource group (MC_ group)
            node_resource_group = self.raw_data.get("node_resource_group")
            if node_resource_group:
                references.append(
                    (f"resource_group:{node_resource_group}", "manages_resource_group")
                )

            # Agent pools / node pools
            agent_pool_profiles = self.raw_data.get("agent_pool_profiles", [])
            for pool in agent_pool_profiles:
                # VM Scale Set reference
                vm_scale_set_id = pool.get("vm_scale_set_id")
                if vm_scale_set_id:
                    references.append((vm_scale_set_id, "has_node_pool"))

                # Subnet reference
                vnet_subnet_id = pool.get("vnet_subnet_id")
                if vnet_subnet_id:
                    references.append((vnet_subnet_id, "uses_subnet"))

            # Network profile
            network_profile = self.raw_data.get("network_profile", {})

            # Load balancer SKU
            load_balancer_sku = network_profile.get("load_balancer_sku")
            if load_balancer_sku:
                references.append((f"lb_sku:{load_balancer_sku}", "uses_lb_sku"))

            # Service CIDR
            service_cidr = network_profile.get("service_cidr")
            if service_cidr:
                references.append((f"cidr:{service_cidr}", "uses_service_cidr"))

            # Identity references
            identity = self.raw_data.get("identity", {})
            if identity.get("type") == "UserAssigned":
                user_assigned_identities = identity.get("user_assigned_identities", {})
                references.extend(
                    (identity_id, "uses_managed_identity")
                    for identity_id in user_assigned_identities
                )

            # Add-on profiles
            addon_profiles = self.raw_data.get("addon_profiles", {})
            for addon_name, addon_config in addon_profiles.items():
                if addon_config.get("enabled") and addon_name == "omsAgent":
                    # Log Analytics workspace for monitoring
                    config = addon_config.get("config", {})
                    workspace_id = config.get("log_analytics_workspace_resource_id")
                    if workspace_id:
                        references.append((workspace_id, "sends_logs_to"))

        return references

    async def list_available_metrics(self) -> list[str]:
        """List available metrics for AKS cluster."""
        return [
            "node_cpu_usage_percentage",
            "node_memory_working_set_percentage",
            "node_disk_usage_percentage",
            "node_network_in_bytes",
            "node_network_out_bytes",
            "kube_pod_status_ready",
            "kube_pod_status_phase",
            "cluster_autoscaler_cluster_safe_to_autoscale",
            "cluster_autoscaler_scale_down_in_cooldown",
            "cluster_autoscaler_unneeded_nodes_count",
            "cluster_autoscaler_unschedulable_pods_count",
        ]

    async def get_metric(
        self,
        metric_name: str,
        time_range_start: AwareDatetime,
        time_range_end: AwareDatetime,
    ) -> list[Observation] | str:
        """Get specific metric data for this AKS cluster."""
        aggregation = "Average"
        if "bytes" in metric_name.lower() or "count" in metric_name.lower():
            aggregation = "Total"

        return await self._get_azure_monitor_metrics(
            metric_names=[metric_name],
            aggregation=aggregation,
            start_time=time_range_start,
            end_time=time_range_end,
            interval="PT5M",
        )

    @property
    def kubernetes_version(self) -> str:
        """Get the Kubernetes version."""
        return self.raw_data.get("kubernetes_version", "") if self.raw_data else ""

    @property
    def dns_prefix(self) -> str:
        """Get the DNS prefix."""
        return self.raw_data.get("dns_prefix", "") if self.raw_data else ""

    @property
    def fqdn(self) -> str:
        """Get the fully qualified domain name."""
        return self.raw_data.get("fqdn", "") if self.raw_data else ""

    @property
    def node_resource_group(self) -> str:
        """Get the node resource group (MC_ group)."""
        return self.raw_data.get("node_resource_group", "") if self.raw_data else ""

    @property
    def provisioning_state(self) -> str:
        """Get the provisioning state."""
        return self.raw_data.get("provisioning_state", "") if self.raw_data else ""

    @property
    def power_state(self) -> dict:
        """Get the power state."""
        return self.raw_data.get("power_state", {}) if self.raw_data else {}

    @property
    def network_profile(self) -> dict:
        """Get the network profile."""
        return self.raw_data.get("network_profile", {}) if self.raw_data else {}

    @property
    def agent_pool_profiles(self) -> list[dict]:
        """Get agent pool profiles."""
        return self.raw_data.get("agent_pool_profiles", []) if self.raw_data else []

    @property
    def addon_profiles(self) -> dict:
        """Get add-on profiles."""
        return self.raw_data.get("addon_profiles", {}) if self.raw_data else {}

    @property
    def sku(self) -> dict:
        """Get the SKU information."""
        return self.raw_data.get("sku", {}) if self.raw_data else {}

    @property
    def max_agent_pools(self) -> int:
        """Get the maximum number of agent pools."""
        return self.raw_data.get("max_agent_pools", 100) if self.raw_data else 100
