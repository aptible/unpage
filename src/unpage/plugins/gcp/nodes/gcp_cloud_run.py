"""Google Cloud Run service node."""

from typing import TYPE_CHECKING

from unpage.knowledge import HasLogs, HasMetrics
from unpage.models import LogLine, Observation
from unpage.plugins.gcp.nodes.base import GcpNode

if TYPE_CHECKING:
    from pydantic import AwareDatetime


class GcpCloudRunService(GcpNode, HasMetrics, HasLogs):
    """A Google Cloud Run service."""

    async def get_identifiers(self) -> list[str | None]:
        """Get unique identifiers for this service."""
        identifiers = await super().get_identifiers()

        # Add service-specific identifiers
        identifiers.extend(
            [
                self.raw_data.get("name"),  # Service name
                self.raw_data.get("uid"),  # Unique ID
            ]
        )

        # Add service URL
        status = self.raw_data.get("status", {})
        if status.get("url"):
            identifiers.append(status["url"])

        # Add traffic URLs
        if status.get("traffic"):
            for traffic in status["traffic"]:
                if traffic.get("url"):
                    identifiers.append(traffic["url"])

        return identifiers

    async def get_reference_identifiers(self) -> list[str | None | tuple[str | None, str]]:
        """Get identifiers that reference other resources."""
        refs = await super().get_reference_identifiers()

        # Add VPC connector reference if configured
        metadata = self.raw_data.get("metadata", {})
        annotations = metadata.get("annotations", {})
        vpc_connector = annotations.get("run.googleapis.com/vpc-access-connector")
        if vpc_connector:
            connector_id = vpc_connector.split("/")[-1]
            refs.append((connector_id, "uses_vpc_connector"))

        # Add service account reference
        spec = self.raw_data.get("spec", {})
        template = spec.get("template", {})
        template_spec = template.get("spec", {})
        service_account = template_spec.get("serviceAccountName")
        if service_account:
            refs.append((service_account, "runs_as"))

        # Add custom domain mapping references
        for domain in annotations.get("run.googleapis.com/domains", "").split(","):
            if domain:
                refs.append((domain.strip(), "mapped_to_domain"))

        return refs

    async def list_available_metrics(self) -> list[str]:
        """List available Cloud Monitoring metrics for this service."""
        return [
            "run.googleapis.com/request_count",
            "run.googleapis.com/request_latencies",
            "run.googleapis.com/container/cpu/utilizations",
            "run.googleapis.com/container/memory/utilizations",
            "run.googleapis.com/container/startup_latencies",
            "run.googleapis.com/container/instance_count",
            "run.googleapis.com/container/cpu/allocation_time",
            "run.googleapis.com/container/memory/allocation_time",
            "run.googleapis.com/container/network/received_bytes_count",
            "run.googleapis.com/container/network/sent_bytes_count",
            "run.googleapis.com/container/billable_instance_time",
        ]

    async def get_metric(
        self,
        metric_name: str,
        time_range_start: "AwareDatetime",
        time_range_end: "AwareDatetime",
    ) -> list[Observation] | str:
        """Get metrics from Cloud Monitoring for this service."""

        metadata = self.raw_data.get("metadata", {})
        service_name = metadata.get("name", "")

        # Extract location from metadata
        location = metadata.get("labels", {}).get("cloud.googleapis.com/location")
        if not location:
            # Try to extract from selfLink or name
            self_link = metadata.get("selfLink", "")
            if "/locations/" in self_link:
                location = self_link.split("/locations/")[1].split("/")[0]

        resource_labels = {
            "service_name": service_name,
            "location": location or "",
            "project_id": self.project_id,
        }

        # Add revision name for revision-specific metrics
        latest_revision = self.raw_data.get("status", {}).get("latestCreatedRevisionName")
        if latest_revision:
            resource_labels["revision_name"] = latest_revision

        return await self._get_cloud_monitoring_metrics(
            metric_type=metric_name,
            resource_type="cloud_run_revision",
            resource_labels=resource_labels,
            start_time=time_range_start,
            end_time=time_range_end,
        )

    async def get_logs(
        self,
        time_range_start: "AwareDatetime",
        time_range_end: "AwareDatetime",
    ) -> list[LogLine]:
        """Get logs from Cloud Logging for this service."""

        metadata = self.raw_data.get("metadata", {})
        service_name = metadata.get("name", "")

        # Build filter for Cloud Run logs
        filter_str = (
            f'resource.type="cloud_run_revision" AND resource.labels.service_name="{service_name}"'
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
        """Get a human-readable display name for this service."""
        metadata = self.raw_data.get("metadata", {})
        return metadata.get("name", "Unknown Cloud Run Service")

    @property
    def location(self) -> str:
        """Get the location (region) of the service."""
        metadata = self.raw_data.get("metadata", {})
        location = metadata.get("labels", {}).get("cloud.googleapis.com/location")
        return location or "unknown"

    @property
    def url(self) -> str | None:
        """Get the service URL."""
        status = self.raw_data.get("status", {})
        return status.get("url")

    @property
    def latest_revision(self) -> str | None:
        """Get the name of the latest revision."""
        status = self.raw_data.get("status", {})
        return status.get("latestCreatedRevisionName")

    @property
    def is_ready(self) -> bool:
        """Check if the service is ready."""
        status = self.raw_data.get("status", {})
        conditions = status.get("conditions", [])
        for condition in conditions:
            if condition.get("type") == "Ready":
                return condition.get("status") == "True"
        return False

    @property
    def traffic_allocation(self) -> dict[str, int]:
        """Get the traffic allocation across revisions."""
        status = self.raw_data.get("status", {})
        traffic = status.get("traffic", [])

        allocation = {}
        for target in traffic:
            revision = target.get("revisionName", "latest")
            percent = target.get("percent", 0)
            allocation[revision] = percent

        return allocation

    @property
    def container_image(self) -> str | None:
        """Get the container image for the service."""
        spec = self.raw_data.get("spec", {})
        template = spec.get("template", {})
        containers = template.get("spec", {}).get("containers", [])

        if containers:
            return containers[0].get("image")
        return None

    @property
    def concurrency(self) -> int:
        """Get the maximum concurrent requests per container."""
        spec = self.raw_data.get("spec", {})
        template = spec.get("template", {})
        container_concurrency = template.get("spec", {}).get("containerConcurrency")

        # Default is 1000 if not specified
        return int(container_concurrency) if container_concurrency else 1000

    @property
    def timeout_seconds(self) -> int:
        """Get the request timeout in seconds."""
        spec = self.raw_data.get("spec", {})
        template = spec.get("template", {})
        timeout = template.get("spec", {}).get("timeoutSeconds")

        # Default is 300 seconds if not specified
        return int(timeout) if timeout else 300

    @property
    def min_instances(self) -> int:
        """Get the minimum number of instances."""
        metadata = self.raw_data.get("metadata", {})
        annotations = metadata.get("annotations", {})
        min_scale = annotations.get("autoscaling.knative.dev/minScale", "0")
        return int(min_scale)

    @property
    def max_instances(self) -> int:
        """Get the maximum number of instances."""
        metadata = self.raw_data.get("metadata", {})
        annotations = metadata.get("annotations", {})
        max_scale = annotations.get("autoscaling.knative.dev/maxScale", "100")
        return int(max_scale)

    @property
    def cpu_limit(self) -> str | None:
        """Get the CPU limit for containers."""
        spec = self.raw_data.get("spec", {})
        template = spec.get("template", {})
        containers = template.get("spec", {}).get("containers", [])

        if containers and "resources" in containers[0]:
            limits = containers[0]["resources"].get("limits", {})
            return limits.get("cpu")
        return None

    @property
    def memory_limit(self) -> str | None:
        """Get the memory limit for containers."""
        spec = self.raw_data.get("spec", {})
        template = spec.get("template", {})
        containers = template.get("spec", {}).get("containers", [])

        if containers and "resources" in containers[0]:
            limits = containers[0]["resources"].get("limits", {})
            return limits.get("memory")
        return None

    @property
    def is_public(self) -> bool:
        """Check if the service allows unauthenticated access."""
        # Check spec for more detailed info - this is a simplified check
        # In reality, you'd need to check IAM policies
        return True  # Default assumption, would need IAM check for accuracy
