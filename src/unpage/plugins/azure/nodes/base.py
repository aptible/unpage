import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING, ClassVar

from azure.core.credentials import TokenCredential
from azure.mgmt.monitor import MonitorManagementClient
from pydantic import BaseModel, Field

from unpage.knowledge import Node
from unpage.models import Observation
from unpage.plugins.azure.resource_id import parse_resource_id
from unpage.plugins.azure.utils import handle_azure_errors

if TYPE_CHECKING:
    from pydantic import AwareDatetime


DEFAULT_AZURE_SUBSCRIPTION_NAME = "default"


class AzureSubscription(BaseModel):
    """Azure subscription configuration."""

    name: str = Field(default=DEFAULT_AZURE_SUBSCRIPTION_NAME)
    subscription_id: str | None = Field(default=None)
    tenant_id: str | None = Field(default=None)

    @property
    def display_name(self) -> str:
        """Get a display name for this subscription."""
        return self.name or self.subscription_id or "Unknown"


class AzureNode(Node):
    """Base class for all Azure nodes."""

    model_config: ClassVar = {"arbitrary_types_allowed": True}

    azure_subscription: AzureSubscription = Field()
    credential: TokenCredential | None = Field(default=None, exclude=True)

    @property
    def resource_id(self) -> str:
        """Get the full Azure Resource ID for this resource."""
        return self.raw_data.get("id", "") if self.raw_data else ""

    @property
    def resource_name(self) -> str:
        """Get the resource name."""
        return self.raw_data.get("name", "") if self.raw_data else ""

    @property
    def resource_group(self) -> str:
        """Get the resource group name from the resource ID."""
        parsed = parse_resource_id(self.resource_id)
        return parsed.resource_group or ""

    @property
    def subscription_id(self) -> str:
        """Get the subscription ID from the resource ID or subscription config."""
        if self.resource_id:
            parsed = parse_resource_id(self.resource_id)
            if parsed.subscription_id:
                return parsed.subscription_id
        return self.azure_subscription.subscription_id or ""

    @property
    def location(self) -> str:
        """Get the Azure region/location for this resource."""
        return self.raw_data.get("location", "") if self.raw_data else ""

    @property
    def resource_type(self) -> str:
        """Get the Azure resource type."""
        parsed = parse_resource_id(self.resource_id)
        return parsed.resource_type or ""

    @property
    def tags(self) -> dict[str, str]:
        """Get resource tags as a dictionary."""
        raw_tags = self.raw_data.get("tags", {}) if self.raw_data else {}
        return dict(raw_tags) if raw_tags else {}

    async def get_identifiers(self) -> list[str | None]:
        """Get all identifiers for this Azure resource."""
        identifiers: list[str | None] = [
            self.resource_id,  # Primary identifier
            self.resource_name,  # Resource name
        ]

        # Add location-specific identifier if available
        if self.location and self.resource_name:
            identifiers.append(f"{self.resource_name}.{self.location}")

        return identifiers

    async def get_reference_identifiers(
        self,
    ) -> list[str | None | tuple[str | None, str]]:
        """Get reference identifiers for relationships with other resources."""
        references: list[str | None | tuple[str | None, str]] = []

        # Add resource group reference
        if self.resource_group:
            references.append((self.resource_group, "in_resource_group"))

        # Add subscription reference
        if self.subscription_id:
            references.append((self.subscription_id, "in_subscription"))

        return references

    async def _get_azure_monitor_metrics(
        self,
        metric_names: list[str],
        aggregation: str = "Average",
        start_time: "AwareDatetime | None" = None,
        end_time: "AwareDatetime | None" = None,
        interval: str = "PT5M",  # 5 minutes
    ) -> list[Observation]:
        """
        Get metrics from Azure Monitor.

        Args:
            metric_names: List of metric names to retrieve
            aggregation: Aggregation type (Average, Maximum, Minimum, Total, etc.)
            start_time: Start time for metrics (defaults to 1 hour ago)
            end_time: End time for metrics (defaults to now)
            interval: ISO 8601 duration for metric intervals

        Returns:
            List of Observation objects with metric data
        """
        if not self.credential or not self.subscription_id:
            return []

        # Set default time range if not provided
        if not end_time:
            end_time = datetime.now(UTC)
        if not start_time:
            start_time = datetime.now(UTC).replace(hour=end_time.hour - 1)  # 1 hour ago

        observations = []

        async with handle_azure_errors("Monitor", f"get metrics for {self.resource_id}"):
            # Create monitor client
            monitor_client = MonitorManagementClient(self.credential, self.subscription_id)

            # Convert metric names to comma-separated string for API call
            metric_names_str = ",".join(metric_names)

            try:
                # Get metrics using asyncio.to_thread for sync API
                response = await asyncio.to_thread(
                    monitor_client.metrics.list,
                    resource_uri=self.resource_id,
                    metricnames=metric_names_str,
                    aggregation=aggregation,
                    timespan=f"{start_time.isoformat()}/{end_time.isoformat()}",
                    interval=interval,
                )

                # Process metrics response
                for metric in response.value:
                    if not metric.timeseries:
                        continue

                    for timeseries in metric.timeseries:
                        if not timeseries.data:
                            continue

                        # Convert timeseries data to Observation format
                        data_points = {}
                        for data_point in timeseries.data:
                            if data_point.time_stamp and hasattr(data_point, aggregation.lower()):
                                value = getattr(data_point, aggregation.lower())
                                if value is not None:
                                    data_points[data_point.time_stamp] = float(value)

                        if data_points:
                            observations.append(
                                Observation(
                                    node_id=self.nid,
                                    observation_type=f"{aggregation} {metric.name.value}",
                                    data=data_points,
                                )
                            )

            except Exception as e:
                # Log error but don't fail - just return empty list
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to get Azure Monitor metrics for {self.resource_id}: {e}")

        return observations

    async def _get_azure_monitor_metric_definitions(self) -> list[str]:
        """
        Get available metric definitions for this resource from Azure Monitor.

        Returns:
            List of available metric names
        """
        if not self.credential or not self.subscription_id:
            return []

        metric_names = []

        async with handle_azure_errors("Monitor", f"get metric definitions for {self.resource_id}"):
            monitor_client = MonitorManagementClient(self.credential, self.subscription_id)

            try:
                # Get metric definitions using asyncio.to_thread for sync API
                response = await asyncio.to_thread(
                    monitor_client.metric_definitions.list,
                    resource_uri=self.resource_id,
                )

                metric_names.extend(
                    [
                        metric_def.name.value
                        for metric_def in response
                        if metric_def.name and metric_def.name.value
                    ]
                )

            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to get metric definitions for {self.resource_id}: {e}")

        return metric_names
