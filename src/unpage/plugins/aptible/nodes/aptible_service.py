from datetime import UTC, datetime

from pydantic import AwareDatetime

from unpage.knowledge import HasMetrics
from unpage.models import Observation
from unpage.plugins.aptible.nodes.aptible_container import AptibleContainer
from unpage.plugins.aptible.nodes.base import AptibleNode


class AptibleService(AptibleNode, HasMetrics):
    """A node representing an Aptible service resource."""

    async def list_available_metrics(self) -> list[str]:
        """Return a list of available metrics for the service."""
        return ["cpu_pct", "la", "memory_all", "iops", "fs"]

    async def get_metric(
        self,
        metric_name: str,
        time_range_start: AwareDatetime,
        time_range_end: AwareDatetime,
    ) -> list[Observation] | str:
        active_containers = await self.get_active_containers(time_range_start, time_range_end)

        if not active_containers:
            return "No active containers found for the time range."

        container_observations = []
        for container in active_containers:
            observations = await container.get_metric(metric_name, time_range_start, time_range_end)

            if not isinstance(observations, list):
                continue

            container_observations.extend(observations)

        return container_observations

    async def get_active_containers(
        self, from_datetime: AwareDatetime, to_datetime: AwareDatetime
    ) -> list[AptibleContainer]:
        """Return a list of containers associated with the service that were active during the specified time range."""
        containers = []

        async for container in self.iter_neighboring(AptibleContainer):
            active_from = datetime.fromisoformat(container.raw_data["created_at"])
            active_to = datetime.fromisoformat(
                container.raw_data.get("deleted_at") or datetime.now(UTC).isoformat()
            )

            # If the alive range overlaps the time range in any way, add the container to the list
            if (
                # Case 1: Either endpoint of the specified period falls within the active range
                (
                    active_from <= from_datetime <= active_to
                    or active_from <= to_datetime <= active_to
                )
                or
                # Case 2: The specified period falls entirely within the active range
                (from_datetime <= active_from and active_to <= to_datetime)
            ):
                containers.append(container)

        # Sort containers by their update_at timestamp, most recent first
        return sorted(containers, key=lambda c: c.raw_data["updated_at"], reverse=True)

    async def _get_stack_name(self) -> str | None:
        """Get the stack name for the service."""
        from .aptible_aws_instance import AptibleAwsInstance
        from .aptible_container import AptibleContainer

        try:
            container = await anext(self.iter_neighboring(AptibleContainer))
            aws_instance = await anext(container.iter_neighboring(AptibleAwsInstance))

            return aws_instance.raw_data["runtime_data"]["stack"]
        except (StopAsyncIteration, KeyError):
            return None
