from pydantic import AwareDatetime

from unpage.knowledge import HasMetrics
from unpage.models import Observation

from .base import AwsNode


class AwsS3Bucket(AwsNode, HasMetrics):
    """An S3 bucket."""

    async def get_identifiers(self) -> list[str | None]:
        return [
            *await super().get_identifiers(),
            self.raw_data["Name"],
            f"arn:aws:s3:::{self.raw_data['Name']}",
        ]

    async def get_reference_identifiers(
        self,
    ) -> list[str | None | tuple[str | None, str]]:
        return [
            *await super().get_reference_identifiers(),
            # S3 buckets might reference VPCs through bucket policies or VPC endpoints
            # but we don't have that information in the basic bucket listing
        ]

    async def list_available_metrics(self) -> list[str]:
        return [
            "BucketSizeBytes",
            "NumberOfObjects",
            "AllRequests",
            "GetRequests",
            "PutRequests",
            "DeleteRequests",
            "HeadRequests",
            "PostRequests",
            "SelectRequests",
            "ListRequests",
        ]

    async def get_metric(
        self,
        metric_name: str,
        time_range_start: AwareDatetime,
        time_range_end: AwareDatetime,
    ) -> list[Observation] | str:
        # S3 metrics are available in CloudWatch with different namespaces
        # BucketSizeBytes and NumberOfObjects are in AWS/S3 namespace
        # Request metrics are in AWS/S3 namespace as well

        if metric_name in ["BucketSizeBytes", "NumberOfObjects"]:
            # Storage metrics have different dimensions
            dimensions = [
                {
                    "Name": "BucketName",
                    "Value": self.raw_data["Name"],
                }
            ]
            if metric_name == "BucketSizeBytes":
                dimensions.append({"Name": "StorageType", "Value": "StandardStorage"})
        else:
            # Request metrics
            dimensions = [
                {
                    "Name": "BucketName",
                    "Value": self.raw_data["Name"],
                }
            ]

        return await self._get_cloudwatch_metric_for_accessible_regions(
            Namespace="AWS/S3",
            MetricName=metric_name,
            Dimensions=dimensions,
            StartTime=time_range_start,
            EndTime=time_range_end,
            Period=300,
            Statistics=["Average", "Minimum", "Maximum"]
            if metric_name not in ["BucketSizeBytes", "NumberOfObjects"]
            else ["Average"],
        )
