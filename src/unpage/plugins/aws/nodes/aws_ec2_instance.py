from pydantic import AwareDatetime

from unpage.knowledge import HasMetrics
from unpage.models import Observation
from unpage.plugins.aws.nodes.base import AwsNode


class AwsEc2Instance(AwsNode, HasMetrics):
    """An EC2 instance."""

    async def get_identifiers(self) -> list[str | None]:
        return [
            *await super().get_identifiers(),
            self.raw_data["InstanceId"],
            self.raw_data.get("PrivateIpAddress"),
            self.raw_data.get("PublicIpAddress"),
            self.raw_data.get("PrivateDnsName"),
            self.raw_data.get("PublicDnsName"),
        ]

    async def get_reference_identifiers(
        self,
    ) -> list[str | None | tuple[str | None, str]]:
        return [
            *await super().get_reference_identifiers(),
            *(sg["GroupId"] for sg in self.raw_data["SecurityGroups"]),
            *((m["Ebs"]["VolumeId"], "has_volume") for m in self.raw_data["BlockDeviceMappings"]),
            self.raw_data.get("VpcId"),
            self.raw_data.get("SubnetId"),
        ]

    async def list_available_metrics(self) -> list[str]:
        return [
            "CPUUtilization",
            "NetworkIn",
            "NetworkOut",
            "StatusCheckFailed",
            "EBSReadBytes",
            "EBSWriteBytes",
        ]

    async def get_metric(
        self,
        metric_name: str,
        time_range_start: AwareDatetime,
        time_range_end: AwareDatetime,
    ) -> list[Observation] | str:
        return await self._get_cloudwatch_metric_for_accessible_regions(
            Namespace="AWS/EC2",
            MetricName=metric_name,
            Dimensions=[{"Name": "InstanceId", "Value": self.raw_data["InstanceId"]}],
            StartTime=time_range_start,
            EndTime=time_range_end,
            Period=300,
            Statistics=["Average", "Minimum", "Maximum"],
        )
