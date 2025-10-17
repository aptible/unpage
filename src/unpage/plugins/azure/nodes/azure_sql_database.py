from pydantic import AwareDatetime

from unpage.knowledge import HasMetrics
from unpage.models import Observation
from unpage.plugins.azure.resource_id import parse_resource_id

from .base import AzureNode


class AzureSqlDatabase(AzureNode, HasMetrics):
    """An Azure SQL Database."""

    async def get_identifiers(self) -> list[str | None]:
        identifiers = [
            *await super().get_identifiers(),
        ]

        if self.raw_data:
            # Add database-specific identifiers
            server_name = self.server_name
            if server_name and self.resource_name:
                identifiers.extend(
                    [
                        f"{server_name}.database.windows.net",
                        f"{self.resource_name}@{server_name}",
                    ]
                )

            # Add collation as an identifier (useful for matching)
            collation = self.raw_data.get("collation")
            if collation:
                identifiers.append(f"{self.resource_name}-{collation}")

        return identifiers

    async def get_reference_identifiers(
        self,
    ) -> list[str | None | tuple[str | None, str]]:
        references = [
            *await super().get_reference_identifiers(),
        ]

        if self.raw_data:
            # Add reference to the SQL server
            server_id = self.server_id
            if server_id:
                references.append((server_id, "hosted_on"))

        return references

    async def list_available_metrics(self) -> list[str]:
        """List available metrics for Azure SQL Database."""
        return [
            "cpu_percent",
            "physical_data_read_percent",
            "log_write_percent",
            "dtu_consumption_percent",
            "storage_percent",
            "connection_successful",
            "connection_failed",
            "blocked_by_firewall",
            "deadlock",
            "storage",
            "xtp_storage_percent",
            "workers_percent",
            "sessions_percent",
            "dtu_limit",
            "dtu_used",
            "dwu_consumption_percent",  # For Data Warehouse
            "dwu_limit",  # For Data Warehouse
        ]

    async def get_metric(
        self,
        metric_name: str,
        time_range_start: AwareDatetime,
        time_range_end: AwareDatetime,
    ) -> list[Observation] | str:
        """Get specific metric data for this Azure SQL Database."""
        return await self._get_azure_monitor_metrics(
            metric_names=[metric_name],
            aggregation="Average",
            start_time=time_range_start,
            end_time=time_range_end,
            interval="PT5M",  # 5 minute intervals
        )

    @property
    def server_name(self) -> str:
        """Get the SQL server name that hosts this database."""
        parsed = parse_resource_id(self.resource_id)
        return parsed.parent_resource or ""

    @property
    def server_id(self) -> str:
        """Get the SQL server resource ID."""
        parsed = parse_resource_id(self.resource_id)
        if parsed.subscription_id and parsed.resource_group and parsed.parent_resource:
            return (
                f"/subscriptions/{parsed.subscription_id}"
                f"/resourceGroups/{parsed.resource_group}"
                f"/providers/Microsoft.Sql"
                f"/servers/{parsed.parent_resource}"
            )
        return ""

    @property
    def edition(self) -> str:
        """Get the database edition (Basic, Standard, Premium, etc.)."""
        return self.raw_data.get("edition", "") if self.raw_data else ""

    @property
    def service_level_objective(self) -> str:
        """Get the service level objective (S0, S1, P1, etc.)."""
        return self.raw_data.get("service_level_objective", "") if self.raw_data else ""

    @property
    def collation(self) -> str:
        """Get the database collation."""
        return self.raw_data.get("collation", "") if self.raw_data else ""

    @property
    def max_size_bytes(self) -> int | None:
        """Get the maximum size of the database in bytes."""
        max_size = self.raw_data.get("max_size_bytes") if self.raw_data else None
        return int(max_size) if max_size is not None else None

    @property
    def status(self) -> str:
        """Get the current database status."""
        return self.raw_data.get("status", "Unknown") if self.raw_data else "Unknown"

    @property
    def creation_date(self) -> str | None:
        """Get the database creation date."""
        creation_date = self.raw_data.get("creation_date") if self.raw_data else None
        if creation_date and hasattr(creation_date, "isoformat"):
            return creation_date.isoformat()
        return str(creation_date) if creation_date else None
