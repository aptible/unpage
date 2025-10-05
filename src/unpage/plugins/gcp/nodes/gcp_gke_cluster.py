"""Google Kubernetes Engine (GKE) cluster node."""

from typing import TYPE_CHECKING

from unpage.knowledge import HasLogs, HasMetrics
from unpage.models import LogLine, Observation
from unpage.plugins.gcp.nodes.base import GcpNode

if TYPE_CHECKING:
    from pydantic import AwareDatetime


class GcpGkeCluster(GcpNode, HasMetrics, HasLogs):
    """A Google Kubernetes Engine cluster."""

    async def get_identifiers(self) -> list[str | None]:
        """Get unique identifiers for this cluster."""
        identifiers = await super().get_identifiers()

        # Add cluster-specific identifiers
        identifiers.extend(
            [
                self.raw_data.get("id"),  # Cluster ID
                self.raw_data.get("name"),  # Cluster name
                self.raw_data.get("selfLink"),  # Full resource URL
                self.raw_data.get("endpoint"),  # Cluster endpoint IP
            ]
        )

        return identifiers

    async def get_reference_identifiers(self) -> list[str | None | tuple[str | None, str]]:
        """Get identifiers that reference other resources."""
        refs = await super().get_reference_identifiers()

        # Add network references
        network = self.raw_data.get("network")
        if network:
            network_id = network.split("/")[-1]
            refs.append((network_id, "in_network"))

        subnetwork = self.raw_data.get("subnetwork")
        if subnetwork:
            subnet_id = subnetwork.split("/")[-1]
            refs.append((subnet_id, "in_subnet"))

        # Add node pool references
        for node_pool in self.raw_data.get("nodePools", []):
            pool_name = node_pool.get("name")
            if pool_name:
                refs.append((f"{self.raw_data.get('name')}-{pool_name}", "has_node_pool"))

        return refs

    async def list_available_metrics(self) -> list[str]:
        """List available Cloud Monitoring metrics for this cluster."""
        return [
            "kubernetes.io/cluster/cpu/allocatable_utilization",
            "kubernetes.io/cluster/cpu/core_usage_time",
            "kubernetes.io/cluster/cpu/allocatable_cores",
            "kubernetes.io/cluster/memory/allocatable_utilization",
            "kubernetes.io/cluster/memory/allocatable_bytes",
            "kubernetes.io/cluster/memory/used_bytes",
            "kubernetes.io/node/cpu/allocatable_utilization",
            "kubernetes.io/node/cpu/core_usage_time",
            "kubernetes.io/node/memory/allocatable_utilization",
            "kubernetes.io/node/memory/used_bytes",
            "kubernetes.io/pod/cpu/core_usage_time",
            "kubernetes.io/pod/memory/used_bytes",
            "kubernetes.io/pod/network/received_bytes_count",
            "kubernetes.io/pod/network/sent_bytes_count",
            "kubernetes.io/container/cpu/core_usage_time",
            "kubernetes.io/container/memory/used_bytes",
            "kubernetes.io/container/restart_count",
        ]

    async def get_metric(
        self,
        metric_name: str,
        time_range_start: "AwareDatetime",
        time_range_end: "AwareDatetime",
    ) -> list[Observation] | str:
        """Get metrics from Cloud Monitoring for this cluster."""

        # Build resource labels
        resource_labels = {
            "cluster_name": self.raw_data.get("name", ""),
            "location": self.raw_data.get("location", ""),
            "project_id": self.project_id,
        }

        # Different resource types for different metrics
        if "cluster" in metric_name:
            resource_type = "k8s_cluster"
        elif "node" in metric_name:
            resource_type = "k8s_node"
        elif "pod" in metric_name:
            resource_type = "k8s_pod"
        elif "container" in metric_name:
            resource_type = "k8s_container"
        else:
            resource_type = "k8s_cluster"

        return await self._get_cloud_monitoring_metrics(
            metric_type=metric_name,
            resource_type=resource_type,
            resource_labels=resource_labels,
            start_time=time_range_start,
            end_time=time_range_end,
        )

    async def get_logs(
        self,
        time_range_start: "AwareDatetime",
        time_range_end: "AwareDatetime",
    ) -> list[LogLine]:
        """Get logs from Cloud Logging for this cluster."""

        cluster_name = self.raw_data.get("name", "")
        location = self.raw_data.get("location", "")

        # Build filter for GKE cluster logs
        filter_str = (
            f'resource.type="k8s_cluster" '
            f'AND resource.labels.cluster_name="{cluster_name}" '
            f'AND resource.labels.location="{location}"'
        )

        logs = await self._get_cloud_logging_logs(
            start_time=time_range_start,
            end_time=time_range_end,
            filter_str=filter_str,
            max_entries=100,
        )

        # Format logs as LogLine objects
        from datetime import datetime

        return [
            LogLine(
                time=datetime.fromisoformat(entry.get("timestamp", "")),
                log=f"[{entry.get('severity', 'INFO')}] {entry.get('textPayload') or str(entry.get('jsonPayload', {}))}",
            )
            for entry in logs
            if entry.get("timestamp")
        ]

    @property
    def display_name(self) -> str:
        """Get a human-readable display name for this cluster."""
        return self.raw_data.get("name", "Unknown GKE Cluster")

    @property
    def status(self) -> str:
        """Get the current status of the cluster."""
        return self.raw_data.get("status", "UNKNOWN")

    @property
    def location(self) -> str:
        """Get the location (zone or region) of the cluster."""
        return self.raw_data.get("location", "unknown")

    @property
    def cluster_version(self) -> str:
        """Get the Kubernetes version of the cluster."""
        return self.raw_data.get("currentMasterVersion", "unknown")

    @property
    def node_version(self) -> str:
        """Get the Kubernetes version of the nodes."""
        return self.raw_data.get("currentNodeVersion", "unknown")

    @property
    def node_count(self) -> int:
        """Get the total number of nodes in the cluster."""
        return int(self.raw_data.get("currentNodeCount", 0))

    @property
    def is_autopilot(self) -> bool:
        """Check if this is an Autopilot cluster."""
        autopilot = self.raw_data.get("autopilot", {})
        return autopilot.get("enabled", False)

    @property
    def is_private_cluster(self) -> bool:
        """Check if this is a private cluster."""
        private_cluster = self.raw_data.get("privateClusterConfig", {})
        return private_cluster.get("enablePrivateNodes", False)


class GcpGkeNodePool(GcpNode, HasMetrics):
    """A GKE cluster node pool."""

    async def get_identifiers(self) -> list[str | None]:
        """Get unique identifiers for this node pool."""
        identifiers = await super().get_identifiers()

        # Add node pool-specific identifiers
        identifiers.extend(
            [
                self.raw_data.get("name"),  # Node pool name
                self.raw_data.get("selfLink"),  # Full resource URL
            ]
        )

        return identifiers

    async def get_reference_identifiers(self) -> list[str | None | tuple[str | None, str]]:
        """Get identifiers that reference other resources."""
        refs = await super().get_reference_identifiers()

        # Reference to the parent cluster
        cluster_name = self.raw_data.get("cluster_name")
        if cluster_name:
            refs.append((cluster_name, "belongs_to_cluster"))

        return refs

    async def list_available_metrics(self) -> list[str]:
        """List available Cloud Monitoring metrics for this node pool."""
        return [
            "kubernetes.io/node/cpu/allocatable_utilization",
            "kubernetes.io/node/cpu/core_usage_time",
            "kubernetes.io/node/memory/allocatable_utilization",
            "kubernetes.io/node/memory/used_bytes",
        ]

    async def get_metric(
        self,
        metric_name: str,
        time_range_start: "AwareDatetime",
        time_range_end: "AwareDatetime",
    ) -> list[Observation] | str:
        """Get metrics from Cloud Monitoring for this node pool."""

        resource_labels = {
            "node_name": self.raw_data.get("name", ""),
            "cluster_name": self.raw_data.get("cluster_name", ""),
            "location": self.raw_data.get("location", ""),
            "project_id": self.project_id,
        }

        return await self._get_cloud_monitoring_metrics(
            metric_type=metric_name,
            resource_type="k8s_node",
            resource_labels=resource_labels,
            start_time=time_range_start,
            end_time=time_range_end,
        )

    @property
    def display_name(self) -> str:
        """Get a human-readable display name for this node pool."""
        return self.raw_data.get("name", "Unknown Node Pool")

    @property
    def status(self) -> str:
        """Get the current status of the node pool."""
        return self.raw_data.get("status", "UNKNOWN")

    @property
    def initial_node_count(self) -> int:
        """Get the initial node count for the pool."""
        return int(self.raw_data.get("initialNodeCount", 0))

    @property
    def autoscaling_enabled(self) -> bool:
        """Check if autoscaling is enabled."""
        autoscaling = self.raw_data.get("autoscaling", {})
        return autoscaling.get("enabled", False)

    @property
    def machine_type(self) -> str:
        """Get the machine type for nodes in this pool."""
        config = self.raw_data.get("config", {})
        return config.get("machineType", "unknown")
