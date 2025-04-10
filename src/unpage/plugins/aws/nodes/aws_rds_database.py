from pydantic import AwareDatetime

from unpage.knowledge import HasMetrics
from unpage.models import Observation

from .base import AwsNode


class AwsRdsDatabase(AwsNode, HasMetrics):
    """An RDS database."""

    async def get_identifiers(self) -> list[str | None]:
        return [
            *await super().get_identifiers(),
            self.raw_data["DBInstanceArn"],
            self.raw_data["DBInstanceIdentifier"],
            self.raw_data["Endpoint"]["Address"],
        ]

    async def get_reference_identifiers(
        self,
    ) -> list[str | None | tuple[str | None, str]]:
        return [
            *await super().get_reference_identifiers(),
            self.raw_data.get("VpcId"),
            *(sg["VpcSecurityGroupId"] for sg in self.raw_data["VpcSecurityGroups"]),
            *(
                (subnet["SubnetIdentifier"], "is_in")
                for subnet in self.raw_data["DBSubnetGroup"]["Subnets"]
            ),
            (
                self.raw_data.get("ReadReplicaSourceDBInstanceIdentifier"),
                "is_replica_of",
            ),
        ]

    async def list_available_metrics(self) -> list[str]:
        return [
            "CPUUtilization",
            "DatabaseConnections",
            "DBLoadRelativeToNumVCPUs",
            "FreeStorageSpace",
            "NetworkReceiveThroughput",
            "ReadIOPS",
            "ReadThroughput",
            "WriteIOPS",
            "WriteThroughput",
        ]

    async def get_metric(
        self,
        metric_name: str,
        time_range_start: AwareDatetime,
        time_range_end: AwareDatetime,
    ) -> list[Observation] | str:
        return await self._get_cloudwatch_metric_for_accessible_regions(
            Namespace="AWS/RDS",
            MetricName=metric_name,
            Dimensions=[
                {
                    "Name": "DBInstanceIdentifier",
                    "Value": self.raw_data["DBInstanceIdentifier"],
                }
            ],
            StartTime=time_range_start,
            EndTime=time_range_end,
            Period=300,
            Statistics=["Average", "Minimum", "Maximum"],
        )
