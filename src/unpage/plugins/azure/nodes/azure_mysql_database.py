from pydantic import AwareDatetime

from unpage.knowledge import HasMetrics
from unpage.models import Observation
from unpage.plugins.azure.resource_id import parse_resource_id

from .base import AzureNode


class AzureMySqlDatabase(AzureNode, HasMetrics):
    """An Azure Database for MySQL database."""

    async def get_identifiers(self) -> list[str | None]:
        identifiers = [
            *await super().get_identifiers(),
        ]

        if self.raw_data:
            # Add MySQL-specific identifiers
            server_name = self.server_name
            if server_name and self.resource_name:
                identifiers.extend(
                    [
                        f"{server_name}.mysql.database.azure.com",
                        f"{self.resource_name}@{server_name}",
                    ]
                )

            # Add charset as identifier
            charset = self.raw_data.get("charset")
            if charset:
                identifiers.append(f"{self.resource_name}-{charset}")

        return identifiers

    async def get_reference_identifiers(
        self,
    ) -> list[str | None | tuple[str | None, str]]:
        references = [
            *await super().get_reference_identifiers(),
        ]

        if self.raw_data:
            # Add reference to the MySQL server
            server_id = self.server_id
            if server_id:
                references.append((server_id, "hosted_on"))

        return references

    async def list_available_metrics(self) -> list[str]:
        """List available metrics for Azure Database for MySQL."""
        return [
            "cpu_percent",
            "memory_percent",
            "io_consumption_percent",
            "storage_percent",
            "storage_used",
            "storage_limit",
            "serverlog_storage_percent",
            "serverlog_storage_usage",
            "serverlog_storage_limit",
            "active_connections",
            "connections_failed",
            "seconds_behind_master",  # For read replicas
            "network_bytes_egress",
            "network_bytes_ingress",
            "backup_storage_used",
        ]

    async def get_metric(
        self,
        metric_name: str,
        time_range_start: AwareDatetime,
        time_range_end: AwareDatetime,
    ) -> list[Observation] | str:
        """Get specific metric data for this MySQL database."""
        return await self._get_azure_monitor_metrics(
            metric_names=[metric_name],
            aggregation="Average",
            start_time=time_range_start,
            end_time=time_range_end,
            interval="PT5M",  # 5 minute intervals
        )

    @property
    def server_name(self) -> str:
        """Get the MySQL server name that hosts this database."""
        parsed = parse_resource_id(self.resource_id)
        return parsed.parent_resource or ""

    @property
    def server_id(self) -> str:
        """Get the MySQL server resource ID."""
        parsed = parse_resource_id(self.resource_id)
        if parsed.subscription_id and parsed.resource_group and parsed.parent_resource:
            return (
                f"/subscriptions/{parsed.subscription_id}"
                f"/resourceGroups/{parsed.resource_group}"
                f"/providers/Microsoft.DBforMySQL"
                f"/servers/{parsed.parent_resource}"
            )
        return ""

    @property
    def charset(self) -> str:
        """Get the database character set."""
        return self.raw_data.get("charset", "") if self.raw_data else ""

    @property
    def collation(self) -> str:
        """Get the database collation."""
        return self.raw_data.get("collation", "") if self.raw_data else ""
