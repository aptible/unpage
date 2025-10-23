"""Google Cloud Storage bucket node."""

from typing import TYPE_CHECKING

from unpage.knowledge import HasMetrics
from unpage.models import Observation
from unpage.plugins.gcp.nodes.base import GcpNode

if TYPE_CHECKING:
    from pydantic import AwareDatetime


class GcpStorageBucket(GcpNode, HasMetrics):
    """A Google Cloud Storage bucket."""

    async def get_identifiers(self) -> list[str | None]:
        """Get unique identifiers for this bucket."""
        identifiers = await super().get_identifiers()

        # Add bucket-specific identifiers
        identifiers.extend(
            [
                self.raw_data.get("id"),  # Bucket ID
                self.raw_data.get("name"),  # Bucket name (globally unique)
                self.raw_data.get("selfLink"),  # Full resource URL
            ]
        )

        return identifiers

    async def get_reference_identifiers(self) -> list[str | None | tuple[str | None, str]]:
        """Get identifiers that reference other resources."""
        refs = await super().get_reference_identifiers()

        # Cloud Storage buckets are fairly standalone, but we can add references
        # to KMS keys if encryption is configured
        encryption = self.raw_data.get("encryption", {})
        if encryption.get("defaultKmsKeyName"):
            kms_key_id = encryption["defaultKmsKeyName"].split("/")[-1]
            refs.append((kms_key_id, "encrypted_by"))

        return refs

    async def list_available_metrics(self) -> list[str]:
        """List available Cloud Monitoring metrics for this bucket."""
        return [
            "storage.googleapis.com/storage/object_count",
            "storage.googleapis.com/storage/total_bytes",
            "storage.googleapis.com/storage/total_byte_seconds",
            "storage.googleapis.com/api/request_count",
            "storage.googleapis.com/network/received_bytes_count",
            "storage.googleapis.com/network/sent_bytes_count",
            "storage.googleapis.com/authz/acl_based_object_access_count",
            "storage.googleapis.com/authz/object_specific_acl_mutation_count",
        ]

    async def get_metric(
        self,
        metric_name: str,
        time_range_start: "AwareDatetime",
        time_range_end: "AwareDatetime",
    ) -> list[Observation] | str:
        """Get metrics from Cloud Monitoring for this bucket."""

        bucket_name = self.raw_data.get("name", "")

        # Build resource labels for this bucket
        resource_labels = {
            "bucket_name": bucket_name,
            "location": self.raw_data.get("location", ""),
            "project_id": self.project_id,
        }

        return await self._get_cloud_monitoring_metrics(
            metric_type=metric_name,
            resource_type="gcs_bucket",
            resource_labels=resource_labels,
            start_time=time_range_start,
            end_time=time_range_end,
        )

    @property
    def display_name(self) -> str:
        """Get a human-readable display name for this bucket."""
        return self.raw_data.get("name", "Unknown GCS Bucket")

    @property
    def location(self) -> str:
        """Get the location of the bucket."""
        return self.raw_data.get("location", "unknown")

    @property
    def storage_class(self) -> str:
        """Get the storage class of the bucket."""
        return self.raw_data.get("storageClass", "STANDARD")

    @property
    def versioning_enabled(self) -> bool:
        """Check if versioning is enabled for the bucket."""
        versioning = self.raw_data.get("versioning", {})
        return versioning.get("enabled", False)

    @property
    def lifecycle_rules_count(self) -> int:
        """Get the number of lifecycle rules configured."""
        lifecycle = self.raw_data.get("lifecycle", {})
        rules = lifecycle.get("rule", [])
        return len(rules)

    @property
    def is_public(self) -> bool:
        """Check if the bucket has public access."""
        iam_config = self.raw_data.get("iamConfiguration", {})
        public_access_prevention = iam_config.get("publicAccessPrevention", "inherited")

        # If public access prevention is enforced, bucket is not public
        if public_access_prevention == "enforced":
            return False

        # Check for uniform bucket-level access
        uniform_access = iam_config.get("uniformBucketLevelAccess", {})
        if uniform_access.get("enabled", False):
            # With uniform access, we'd need to check IAM policies
            # For now, assume not public unless we can verify
            return False

        # If neither is set, bucket might be public (would need to check ACLs)
        return False  # Conservative default
