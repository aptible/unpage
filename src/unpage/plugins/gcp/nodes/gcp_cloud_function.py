"""Google Cloud Functions node."""

from typing import TYPE_CHECKING

from unpage.knowledge import HasLogs, HasMetrics
from unpage.models import LogLine, Observation
from unpage.plugins.gcp.nodes.base import GcpNode

if TYPE_CHECKING:
    from pydantic import AwareDatetime


class GcpCloudFunction(GcpNode, HasMetrics, HasLogs):
    """A Google Cloud Function (1st or 2nd generation)."""

    async def get_identifiers(self) -> list[str | None]:
        """Get unique identifiers for this function."""
        identifiers = await super().get_identifiers()

        # Add function-specific identifiers
        identifiers.extend(
            [
                self.raw_data.get("name"),  # Function name (full path)
                self.raw_data.get("httpsTrigger", {}).get("url"),  # HTTP trigger URL if available
            ]
        )

        # For v2 functions
        if "serviceConfig" in self.raw_data:
            identifiers.append(self.raw_data["serviceConfig"].get("uri"))

        return identifiers

    async def get_reference_identifiers(self) -> list[str | None | tuple[str | None, str]]:
        """Get identifiers that reference other resources."""
        refs = await super().get_reference_identifiers()

        # Add VPC connector reference if configured
        vpc_connector = self.raw_data.get("vpcConnector")
        if vpc_connector:
            connector_id = vpc_connector.split("/")[-1]
            refs.append((connector_id, "uses_vpc_connector"))

        # For v2 functions, check service config
        service_config = self.raw_data.get("serviceConfig", {})
        if service_config.get("vpcConnector"):
            connector_id = service_config["vpcConnector"].split("/")[-1]
            refs.append((connector_id, "uses_vpc_connector"))

        # Add service account reference
        service_account = self.raw_data.get("serviceAccountEmail")
        if not service_account and "serviceConfig" in self.raw_data:
            service_account = self.raw_data["serviceConfig"].get("serviceAccountEmail")
        if service_account:
            refs.append((service_account, "runs_as"))

        # Add source repository reference if available
        source_repo = self.raw_data.get("sourceRepository", {})
        if source_repo.get("url"):
            refs.append((source_repo["url"], "source_from"))

        return refs

    async def list_available_metrics(self) -> list[str]:
        """List available Cloud Monitoring metrics for this function."""
        # Check if this is a v2 function
        is_v2 = "serviceConfig" in self.raw_data

        if is_v2:
            return [
                "cloudfunctionsv2.googleapis.com/function/execution_count",
                "cloudfunctionsv2.googleapis.com/function/execution_time",
                "cloudfunctionsv2.googleapis.com/function/active_instances",
                "cloudfunctionsv2.googleapis.com/function/memory_usage",
                "cloudfunctionsv2.googleapis.com/function/network_egress",
                "cloudfunctionsv2.googleapis.com/function/billable_time",
            ]
        else:
            return [
                "cloudfunctions.googleapis.com/function/execution_count",
                "cloudfunctions.googleapis.com/function/execution_times",
                "cloudfunctions.googleapis.com/function/active_instances",
                "cloudfunctions.googleapis.com/function/user_memory_bytes",
                "cloudfunctions.googleapis.com/function/network_egress",
            ]

    async def get_metric(
        self,
        metric_name: str,
        time_range_start: "AwareDatetime",
        time_range_end: "AwareDatetime",
    ) -> list[Observation] | str:
        """Get metrics from Cloud Monitoring for this function."""

        # Extract function name from the full path
        function_name = self.raw_data.get("name", "").split("/")[-1]

        # Get region from name or location
        location = self.raw_data.get("location")
        if not location and "/" in self.raw_data.get("name", ""):
            # Extract from name like projects/X/locations/Y/functions/Z
            parts = self.raw_data["name"].split("/")
            if len(parts) >= 4:
                location = parts[3]

        resource_labels = {
            "function_name": function_name,
            "region": location or "",
            "project_id": self.project_id,
        }

        # Determine resource type based on function generation
        is_v2 = "serviceConfig" in self.raw_data
        resource_type = (
            "cloudfunctions.googleapis.com" if not is_v2 else "cloudfunctionsv2.googleapis.com"
        )

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
        """Get logs from Cloud Logging for this function."""

        function_name = self.raw_data.get("name", "").split("/")[-1]

        # Build filter for function logs
        filter_str = (
            f'resource.type="cloud_function" AND resource.labels.function_name="{function_name}"'
        )

        # For v2 functions, might need different resource type
        if "serviceConfig" in self.raw_data:
            filter_str = (
                f'(resource.type="cloud_function" OR resource.type="cloud_run_revision") '
                f'AND labels."goog-managed-by"="cloudfunctions" '
                f'AND resource.labels.function_name="{function_name}"'
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
        """Get a human-readable display name for this function."""
        # Extract just the function name from the full path
        full_name = self.raw_data.get("name", "Unknown Function")
        return full_name.split("/")[-1]

    @property
    def status(self) -> str:
        """Get the current status of the function."""
        # v2 functions have state, v1 have status
        return self.raw_data.get("state") or self.raw_data.get("status", "UNKNOWN")

    @property
    def runtime(self) -> str:
        """Get the runtime environment."""
        # For v2, it's in buildConfig
        if "buildConfig" in self.raw_data:
            return self.raw_data["buildConfig"].get("runtime", "unknown")
        return self.raw_data.get("runtime", "unknown")

    @property
    def entry_point(self) -> str:
        """Get the function entry point."""
        # For v2, it's in buildConfig
        if "buildConfig" in self.raw_data:
            return self.raw_data["buildConfig"].get("entryPoint", "unknown")
        return self.raw_data.get("entryPoint", "unknown")

    @property
    def timeout(self) -> str:
        """Get the function timeout."""
        # For v2, it's in serviceConfig
        if "serviceConfig" in self.raw_data:
            return self.raw_data["serviceConfig"].get("timeoutSeconds", "60")
        return self.raw_data.get("timeout", "60s")

    @property
    def available_memory_mb(self) -> int:
        """Get the available memory in MB."""
        # For v2, it's in serviceConfig
        if "serviceConfig" in self.raw_data:
            memory = self.raw_data["serviceConfig"].get("availableMemory", "256M")
            # Parse memory string like "256M" or "1G"
            if memory.endswith("G"):
                return int(memory[:-1]) * 1024
            elif memory.endswith("M"):
                return int(memory[:-1])
            return 256
        return int(self.raw_data.get("availableMemoryMb", 256))

    @property
    def max_instances(self) -> int:
        """Get the maximum number of instances."""
        # For v2, it's in serviceConfig
        if "serviceConfig" in self.raw_data:
            return int(self.raw_data["serviceConfig"].get("maxInstanceCount", 0))
        return int(self.raw_data.get("maxInstances", 0))

    @property
    def trigger_type(self) -> str:
        """Get the trigger type for this function."""
        if self.raw_data.get("httpsTrigger"):
            return "HTTPS"
        elif self.raw_data.get("eventTrigger"):
            event_trigger = self.raw_data["eventTrigger"]
            return f"Event: {event_trigger.get('eventType', 'unknown')}"
        elif "eventTrigger" in self.raw_data.get("serviceConfig", {}):
            event_trigger = self.raw_data["serviceConfig"]["eventTrigger"]
            return f"Event: {event_trigger.get('eventType', 'unknown')}"
        return "Unknown"

    @property
    def is_gen2(self) -> bool:
        """Check if this is a 2nd generation function."""
        return "serviceConfig" in self.raw_data or self.raw_data.get("environment") == "GEN_2"
