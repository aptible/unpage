"""Google Cloud SQL instance node."""

from typing import TYPE_CHECKING

from unpage.knowledge import HasLogs, HasMetrics
from unpage.models import LogLine, Observation
from unpage.plugins.gcp.nodes.base import GcpNode

if TYPE_CHECKING:
    from pydantic import AwareDatetime


class GcpCloudSqlInstance(GcpNode, HasMetrics, HasLogs):
    """A Google Cloud SQL database instance."""

    async def get_identifiers(self) -> list[str | None]:
        """Get unique identifiers for this instance."""
        identifiers = await super().get_identifiers()

        # Add Cloud SQL-specific identifiers
        identifiers.extend(
            [
                self.raw_data.get("name"),  # Instance name
                self.raw_data.get("selfLink"),  # Full resource URL
                self.raw_data.get("connectionName"),  # Connection name for Cloud SQL Proxy
            ]
        )

        # Add IP addresses
        for ip_address in self.raw_data.get("ipAddresses", []):
            identifiers.append(ip_address.get("ipAddress"))

        return identifiers

    async def get_reference_identifiers(self) -> list[str | None | tuple[str | None, str]]:
        """Get identifiers that reference other resources."""
        refs = await super().get_reference_identifiers()

        # Add master instance reference if this is a replica
        master_instance = self.raw_data.get("masterInstanceName")
        if master_instance:
            refs.append((master_instance, "replica_of"))

        # Add replica references if this is a master
        for replica in self.raw_data.get("replicaNames", []):
            refs.append((replica, "has_replica"))

        # Add network reference if using private IP
        ip_config = self.raw_data.get("settings", {}).get("ipConfiguration", {})
        private_network = ip_config.get("privateNetwork")
        if private_network:
            network_id = private_network.split("/")[-1]
            refs.append((network_id, "in_network"))

        return refs

    async def list_available_metrics(self) -> list[str]:
        """List available Cloud Monitoring metrics for this instance."""
        return [
            "cloudsql.googleapis.com/database/cpu/utilization",
            "cloudsql.googleapis.com/database/cpu/usage_time",
            "cloudsql.googleapis.com/database/disk/bytes_used",
            "cloudsql.googleapis.com/database/disk/quota",
            "cloudsql.googleapis.com/database/disk/read_ops_count",
            "cloudsql.googleapis.com/database/disk/write_ops_count",
            "cloudsql.googleapis.com/database/memory/utilization",
            "cloudsql.googleapis.com/database/memory/usage",
            "cloudsql.googleapis.com/database/memory/quota",
            "cloudsql.googleapis.com/database/network/connections",
            "cloudsql.googleapis.com/database/network/received_bytes_count",
            "cloudsql.googleapis.com/database/network/sent_bytes_count",
            "cloudsql.googleapis.com/database/replication/replica_lag",
            "cloudsql.googleapis.com/database/up",
            "cloudsql.googleapis.com/database/uptime",
        ]

    async def get_metric(
        self,
        metric_name: str,
        time_range_start: "AwareDatetime",
        time_range_end: "AwareDatetime",
    ) -> list[Observation] | str:
        """Get metrics from Cloud Monitoring for this instance."""

        # Build resource labels for this instance
        resource_labels = {
            "database_id": f"{self.project_id}:{self.raw_data.get('name', '')}",
            "region": self.raw_data.get("region", ""),
            "project_id": self.project_id,
        }

        return await self._get_cloud_monitoring_metrics(
            metric_type=metric_name,
            resource_type="cloudsql_database",
            resource_labels=resource_labels,
            start_time=time_range_start,
            end_time=time_range_end,
        )

    async def get_logs(
        self,
        time_range_start: "AwareDatetime",
        time_range_end: "AwareDatetime",
    ) -> list[LogLine]:
        """Get logs from Cloud Logging for this instance."""

        instance_name = self.raw_data.get("name", "")

        # Build filter for this specific Cloud SQL instance
        filter_str = (
            f'resource.type="cloudsql_database" '
            f'AND resource.labels.database_id="{self.project_id}:{instance_name}"'
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
        """Get a human-readable display name for this instance."""
        return self.raw_data.get("name", "Unknown Cloud SQL Instance")

    @property
    def database_version(self) -> str:
        """Get the database version (e.g., MYSQL_8_0, POSTGRES_14)."""
        return self.raw_data.get("databaseVersion", "unknown")

    @property
    def state(self) -> str:
        """Get the current state of the instance."""
        return self.raw_data.get("state", "UNKNOWN")

    @property
    def region(self) -> str:
        """Get the region where the instance is located."""
        return self.raw_data.get("region", "unknown")

    @property
    def tier(self) -> str:
        """Get the machine type tier."""
        settings = self.raw_data.get("settings", {})
        return settings.get("tier", "unknown")

    @property
    def disk_size_gb(self) -> int:
        """Get the disk size in GB."""
        settings = self.raw_data.get("settings", {})
        data_disk = settings.get("dataDiskSizeGb", 0)
        return int(data_disk)

    @property
    def is_replica(self) -> bool:
        """Check if this is a replica instance."""
        return self.raw_data.get("masterInstanceName") is not None

    @property
    def backup_enabled(self) -> bool:
        """Check if automatic backups are enabled."""
        settings = self.raw_data.get("settings", {})
        backup_config = settings.get("backupConfiguration", {})
        return backup_config.get("enabled", False)

    @property
    def high_availability(self) -> bool:
        """Check if high availability is enabled."""
        settings = self.raw_data.get("settings", {})
        availability_type = settings.get("availabilityType", "ZONAL")
        return availability_type == "REGIONAL"
