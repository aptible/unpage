from pydantic import AwareDatetime

from unpage.knowledge import HasMetrics
from unpage.models import Observation

from .base import AzureNode


class AzureStorageAccount(AzureNode, HasMetrics):
    """An Azure Storage Account."""

    async def get_identifiers(self) -> list[str | None]:
        identifiers = [
            *await super().get_identifiers(),
        ]

        if self.raw_data:
            # Add storage account endpoints
            primary_endpoints = self.raw_data.get("primary_endpoints", {})
            identifiers.extend([endpoint for endpoint in primary_endpoints.values() if endpoint])

            # Add secondary endpoints if available
            secondary_endpoints = self.raw_data.get("secondary_endpoints", {})
            identifiers.extend([endpoint for endpoint in secondary_endpoints.values() if endpoint])

            # Add custom domain if configured
            custom_domain = self.raw_data.get("custom_domain", {})
            if custom_domain and custom_domain.get("name"):
                identifiers.append(custom_domain["name"])

        return identifiers

    async def get_reference_identifiers(
        self,
    ) -> list[str | None | tuple[str | None, str]]:
        references = [
            *await super().get_reference_identifiers(),
        ]

        if self.raw_data:
            # Add network rule set references
            network_rule_set = self.raw_data.get("network_rule_set", {})
            if network_rule_set:
                # Virtual network rules
                virtual_network_rules = network_rule_set.get("virtual_network_rules", [])
                for rule in virtual_network_rules:
                    subnet_id = rule.get("virtual_network_resource_id")
                    if subnet_id:
                        references.append((subnet_id, "allowed_from_subnet"))

                # Private endpoint connections
                private_endpoint_connections = self.raw_data.get("private_endpoint_connections", [])
                for connection in private_endpoint_connections:
                    pe_id = connection.get("private_endpoint", {}).get("id")
                    if pe_id:
                        references.append((pe_id, "connected_to_private_endpoint"))

        return references

    async def list_available_metrics(self) -> list[str]:
        """List available metrics for Azure Storage Account."""
        return [
            # Account-level metrics
            "UsedCapacity",
            "Transactions",
            "Ingress",
            "Egress",
            "SuccessServerLatency",
            "SuccessE2ELatency",
            "Availability",
            # Blob service metrics
            "BlobCapacity",
            "BlobCount",
            "ContainerCount",
            # File service metrics
            "FileCapacity",
            "FileCount",
            "FileShareCount",
            "FileShareSnapshotCount",
            "FileShareSnapshotSize",
            "FileShareCapacityQuota",
            # Queue service metrics
            "QueueCapacity",
            "QueueCount",
            "QueueMessageCount",
            # Table service metrics
            "TableCapacity",
            "TableCount",
            "TableEntityCount",
        ]

    async def get_metric(
        self,
        metric_name: str,
        time_range_start: AwareDatetime,
        time_range_end: AwareDatetime,
    ) -> list[Observation] | str:
        """Get specific metric data for this Azure Storage Account."""
        # Use appropriate aggregation based on metric type
        aggregation = "Average"
        if metric_name in ["Transactions", "Ingress", "Egress"]:
            aggregation = "Total"
        elif metric_name in [
            "UsedCapacity",
            "BlobCapacity",
            "FileCapacity",
            "QueueCapacity",
            "TableCapacity",
        ]:
            aggregation = "Average"

        return await self._get_azure_monitor_metrics(
            metric_names=[metric_name],
            aggregation=aggregation,
            start_time=time_range_start,
            end_time=time_range_end,
            interval="PT1H",  # 1 hour intervals for storage metrics
        )

    @property
    def sku_name(self) -> str:
        """Get the storage account SKU (Standard_LRS, Premium_LRS, etc.)."""
        sku = self.raw_data.get("sku", {}) if self.raw_data else {}
        return sku.get("name", "")

    @property
    def sku_tier(self) -> str:
        """Get the storage account SKU tier (Standard, Premium)."""
        sku = self.raw_data.get("sku", {}) if self.raw_data else {}
        return sku.get("tier", "")

    @property
    def kind(self) -> str:
        """Get the storage account kind (Storage, StorageV2, BlobStorage, etc.)."""
        return self.raw_data.get("kind", "") if self.raw_data else ""

    @property
    def access_tier(self) -> str:
        """Get the access tier (Hot, Cool, Archive)."""
        return self.raw_data.get("access_tier", "") if self.raw_data else ""

    @property
    def provisioning_state(self) -> str:
        """Get the provisioning state."""
        return self.raw_data.get("provisioning_state", "") if self.raw_data else ""

    @property
    def status_of_primary(self) -> str:
        """Get the status of primary location."""
        return self.raw_data.get("status_of_primary", "") if self.raw_data else ""

    @property
    def status_of_secondary(self) -> str:
        """Get the status of secondary location."""
        return self.raw_data.get("status_of_secondary", "") if self.raw_data else ""

    @property
    def primary_location(self) -> str:
        """Get the primary location."""
        return self.raw_data.get("primary_location", "") if self.raw_data else ""

    @property
    def secondary_location(self) -> str:
        """Get the secondary location."""
        return self.raw_data.get("secondary_location", "") if self.raw_data else ""

    @property
    def primary_endpoints(self) -> dict:
        """Get primary service endpoints."""
        return self.raw_data.get("primary_endpoints", {}) if self.raw_data else {}

    @property
    def secondary_endpoints(self) -> dict:
        """Get secondary service endpoints."""
        return self.raw_data.get("secondary_endpoints", {}) if self.raw_data else {}

    @property
    def custom_domain(self) -> dict:
        """Get custom domain configuration."""
        return self.raw_data.get("custom_domain", {}) if self.raw_data else {}

    @property
    def encryption(self) -> dict:
        """Get encryption configuration."""
        return self.raw_data.get("encryption", {}) if self.raw_data else {}

    @property
    def network_rule_set(self) -> dict:
        """Get network access rules."""
        return self.raw_data.get("network_rule_set", {}) if self.raw_data else {}

    @property
    def is_https_traffic_only_enabled(self) -> bool:
        """Check if HTTPS-only traffic is enabled."""
        return self.raw_data.get("enable_https_traffic_only", False) if self.raw_data else False

    @property
    def allow_blob_public_access(self) -> bool:
        """Check if blob public access is allowed."""
        return self.raw_data.get("allow_blob_public_access", True) if self.raw_data else True

    @property
    def minimum_tls_version(self) -> str:
        """Get the minimum TLS version."""
        return self.raw_data.get("minimum_tls_version", "") if self.raw_data else ""

    @property
    def creation_time(self) -> str | None:
        """Get the storage account creation time."""
        creation_time = self.raw_data.get("creation_time") if self.raw_data else None
        if creation_time and hasattr(creation_time, "isoformat"):
            return creation_time.isoformat()
        return str(creation_time) if creation_time else None

    @property
    def blob_endpoint(self) -> str:
        """Get the blob service endpoint."""
        endpoints = self.primary_endpoints
        return endpoints.get("blob", "")

    @property
    def file_endpoint(self) -> str:
        """Get the file service endpoint."""
        endpoints = self.primary_endpoints
        return endpoints.get("file", "")

    @property
    def queue_endpoint(self) -> str:
        """Get the queue service endpoint."""
        endpoints = self.primary_endpoints
        return endpoints.get("queue", "")

    @property
    def table_endpoint(self) -> str:
        """Get the table service endpoint."""
        endpoints = self.primary_endpoints
        return endpoints.get("table", "")
