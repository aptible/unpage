from pydantic import AwareDatetime

from unpage.knowledge import HasMetrics
from unpage.models import Observation

from .base import AzureNode


class AzureCosmosDb(AzureNode, HasMetrics):
    """An Azure Cosmos DB account."""

    async def get_identifiers(self) -> list[str | None]:
        identifiers = [
            *await super().get_identifiers(),
        ]

        if self.raw_data:
            # Add Cosmos DB-specific identifiers
            document_endpoint = self.raw_data.get("document_endpoint")
            if document_endpoint:
                identifiers.append(document_endpoint)

            # Add write locations
            write_locations = self.raw_data.get("write_locations", [])
            for location in write_locations:
                endpoint = location.get("document_endpoint")
                if endpoint:
                    identifiers.append(endpoint)

            # Add read locations
            read_locations = self.raw_data.get("read_locations", [])
            for location in read_locations:
                endpoint = location.get("document_endpoint")
                if endpoint:
                    identifiers.append(endpoint)

        return identifiers

    async def get_reference_identifiers(
        self,
    ) -> list[str | None | tuple[str | None, str]]:
        references = [
            *await super().get_reference_identifiers(),
        ]

        if self.raw_data:
            # Add virtual network rule references
            virtual_network_rules = self.raw_data.get("virtual_network_rules", [])
            for rule in virtual_network_rules:
                subnet_id = rule.get("id")
                if subnet_id:
                    references.append((subnet_id, "allowed_from_subnet"))

        return references

    async def list_available_metrics(self) -> list[str]:
        """List available metrics for Azure Cosmos DB."""
        return [
            "TotalRequestUnits",
            "TotalRequests",
            "MongoRequests",
            "MongoRequestCharge",
            "AutoscaleMaxThroughput",
            "ProvisionedThroughput",
            "AvailableStorage",
            "DataUsage",
            "IndexUsage",
            "DocumentCount",
            "DocumentQuota",
            "MetadataRequests",
            "ReplicationLatency",
            "ServiceAvailability",
            "CassandraRequests",
            "CassandraRequestCharges",
            "GremlinRequests",
            "GremlinRequestCharges",
            "SqlRequests",
            "SqlRequestCharges",
        ]

    async def get_metric(
        self,
        metric_name: str,
        time_range_start: AwareDatetime,
        time_range_end: AwareDatetime,
    ) -> list[Observation] | str:
        """Get specific metric data for this Cosmos DB account."""
        return await self._get_azure_monitor_metrics(
            metric_names=[metric_name],
            aggregation="Total"
            if "Requests" in metric_name or "RequestUnits" in metric_name
            else "Average",
            start_time=time_range_start,
            end_time=time_range_end,
            interval="PT5M",  # 5 minute intervals
        )

    @property
    def document_endpoint(self) -> str:
        """Get the primary document endpoint URL."""
        return self.raw_data.get("document_endpoint", "") if self.raw_data else ""

    @property
    def kind(self) -> str:
        """Get the Cosmos DB account kind (GlobalDocumentDB, MongoDB, Parse)."""
        return self.raw_data.get("kind", "") if self.raw_data else ""

    @property
    def database_account_offer_type(self) -> str:
        """Get the offer type for the database account."""
        return self.raw_data.get("database_account_offer_type", "") if self.raw_data else ""

    @property
    def consistency_policy(self) -> dict:
        """Get the consistency policy settings."""
        return self.raw_data.get("consistency_policy", {}) if self.raw_data else {}

    @property
    def write_locations(self) -> list[dict]:
        """Get the write locations for this Cosmos DB account."""
        return self.raw_data.get("write_locations", []) if self.raw_data else []

    @property
    def read_locations(self) -> list[dict]:
        """Get the read locations for this Cosmos DB account."""
        return self.raw_data.get("read_locations", []) if self.raw_data else []

    @property
    def failover_policies(self) -> list[dict]:
        """Get the failover policies."""
        return self.raw_data.get("failover_policies", []) if self.raw_data else []

    @property
    def is_virtual_network_filter_enabled(self) -> bool:
        """Check if virtual network filtering is enabled."""
        return (
            self.raw_data.get("is_virtual_network_filter_enabled", False)
            if self.raw_data
            else False
        )

    @property
    def enable_automatic_failover(self) -> bool:
        """Check if automatic failover is enabled."""
        return self.raw_data.get("enable_automatic_failover", False) if self.raw_data else False

    @property
    def enable_multiple_write_locations(self) -> bool:
        """Check if multiple write locations are enabled."""
        return (
            self.raw_data.get("enable_multiple_write_locations", False) if self.raw_data else False
        )
