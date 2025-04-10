import json
from typing import cast

from pydantic import AwareDatetime

from unpage.knowledge import NODE_REGISTRY, HasMetrics
from unpage.lib.anomalies import Anomaly, Point, detect_anomalies
from unpage.models import Observation
from unpage.plugins.base import Plugin
from unpage.plugins.mixins import McpServerMixin, tool


class MetricsPlugin(Plugin, McpServerMixin):
    @tool()
    async def list_node_types_that_support_metrics(self) -> list[str]:
        """List the types of nodes that support metrics retrieval.

        This is useful for getting a list of node types that you can use in
        metrics_get_metrics_for_resource.

        Use this before attempting to get metrics for a resource.
        """
        return [
            f"{node_cls._node_source}:{node_cls._node_type}"
            for node_cls in NODE_REGISTRY.values()
            if issubclass(node_cls, HasMetrics)
        ]

    @tool()
    async def list_available_metrics_for_node(self, node_id: str) -> list[str] | str:
        """List the available metrics for a node."""
        node = await self.context.graph.get_node(node_id)

        if not isinstance(node, HasMetrics):
            return f"{node.node_type} nodes do not support metrics"

        return await node.list_available_metrics()

    @tool()
    async def get_metrics_for_node(
        self,
        node_id: str,
        time_range_start: AwareDatetime,
        time_range_end: AwareDatetime,
        metric_names: list[str] | str | None = None,
    ) -> list[Observation] | str:
        """Get metrics for a resource using its node ID.

        A good starting point for the length of the time range is an hour.

        You can get valid metric names for a node using the
        list_available_metrics_for_node tool.

        Metric names should be provided as a JSON array of strings.
        """
        node = await self.context.graph.get_node(node_id)

        if not node:
            return f"Resource with node ID {node_id} not found"

        if not isinstance(node, HasMetrics):
            return f"{node.node_type} nodes do not support metrics"

        metric_names = metric_names if metric_names else await node.list_available_metrics()

        # HACK: Some LLM clients send the metric names as a JSON string, which
        # we need to parse into a list.
        if isinstance(metric_names, str):
            try:
                metric_names = json.loads(metric_names)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"metric_names should be a valid JSON array, got {metric_names}"
                ) from e

        observations = await node.get_metrics(
            metric_names=cast("list[str]", metric_names),
            time_range_start=time_range_start,
            time_range_end=time_range_end,
        )

        return observations or "No metrics found. Try a longer time range."

    @tool(
        description=(
            """Get anomalies for a list of metrics. Once you have the results
            from metrics_get_metrics_for_resource, you can send a list of
            Points (timestamp and value pairs) to this tool to identify
            anomalies."""
        )
    )
    async def get_anomalies_for_metrics(
        self,
        metrics: list[Point],
    ) -> list[Anomaly]:
        return detect_anomalies(metrics)
