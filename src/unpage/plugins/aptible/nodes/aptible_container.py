from pydantic import AwareDatetime

from unpage.knowledge import HasMetrics
from unpage.models import Observation
from unpage.plugins.aptible.client import AptibleMetricsClient
from unpage.plugins.aptible.nodes.base import AptibleNode


class AptibleContainer(AptibleNode, HasMetrics):
    """A container running on an Aptible service."""

    async def get_identifiers(self) -> list[str | None]:
        """Return a list of unique identifiers for the container."""
        return [
            *await super().get_identifiers(),
            self.raw_data["docker_name"],
        ]

    async def get_reference_identifiers(
        self,
    ) -> list[str | None | tuple[str | None, str]]:
        """Return a list of identifiers that potentially reference other nodes."""
        return [
            *await super().get_reference_identifiers(),
            (self.raw_data["aws_instance_id"], "running_on"),
            (self.raw_data["host"], "running_on"),
        ]

    async def list_available_metrics(self) -> list[str]:
        """Return a list of available metrics for the container."""
        metrics = ["cpu_pct", "la", "memory_all"]

        # If the container has mounts, add disk-related metrics.
        if self.raw_data["mounts"]:
            metrics = [*metrics, "iops", "fs"]

        return metrics

    async def get_metric(
        self,
        metric_name: str,
        time_range_start: AwareDatetime,
        time_range_end: AwareDatetime,
    ) -> list[Observation] | str:
        """Return a metric for the container."""
        metrics_client = AptibleMetricsClient()

        container_id = str(self.raw_data["id"])
        observations = await metrics_client.get_metrics(
            self.nid, [container_id], metric_name, time_range_start, time_range_end
        )
        return observations or "No metrics data found for the time range."

    async def _get_stack_name(self) -> str | None:
        """Get the stack name for the container."""
        from .aptible_aws_instance import AptibleAwsInstance

        try:
            aws_instance = await anext(self.iter_neighboring(AptibleAwsInstance))
            return aws_instance.raw_data["runtime_data"]["stack"]
        except (StopAsyncIteration, KeyError):
            return None
