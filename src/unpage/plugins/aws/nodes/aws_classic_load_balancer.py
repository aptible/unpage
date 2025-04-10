from pydantic import AwareDatetime

from unpage.knowledge import HasMetrics
from unpage.models import Observation

from .base import AwsNode


class AwsClassicLoadBalancer(AwsNode, HasMetrics):
    async def get_identifiers(self) -> list[str | None]:
        return [
            *await super().get_identifiers(),
            self.raw_data["LoadBalancerName"],
            self.raw_data["DNSName"],
        ]

    async def get_reference_identifiers(
        self,
    ) -> list[str | None | tuple[str | None, str]]:
        return [
            *await super().get_reference_identifiers(),
            self.raw_data.get("VpcId"),
            *self.raw_data["Subnets"],
            *self.raw_data["SecurityGroups"],
            *((i["InstanceId"], "routes_to") for i in self.raw_data["Instances"]),
        ]

    async def list_available_metrics(self) -> list[str]:
        return [
            "RequestCount",
            "HTTPCode_Backend_2XX",
            "HTTPCode_Backend_3XX",
            "HTTPCode_Backend_4XX",
            "HTTPCode_Backend_5XX",
            "HealthyHostCount",
            "UnHealthyHostCount",
            "Latency",
        ]

    async def get_metric(
        self,
        metric_name: str,
        time_range_start: AwareDatetime,
        time_range_end: AwareDatetime,
    ) -> list[Observation] | str:
        # Define appropriate statistics based on metric type
        if metric_name in [
            "RequestCount",
            "HTTPCode_Backend_2XX",
            "HTTPCode_Backend_3XX",
            "HTTPCode_Backend_4XX",
            "HTTPCode_Backend_5XX",
        ]:
            # Count-based metrics primarily use Sum
            statistics = ["Sum"]
        elif metric_name == "Latency":
            # Latency benefits from Average and percentiles
            statistics = ["Average", "p50", "p90", "p95", "p99"]
        elif metric_name in ["HealthyHostCount", "UnHealthyHostCount"]:
            # Host count metrics use Average, Min, and Max
            statistics = ["Average", "Minimum", "Maximum"]
        else:
            # Default statistics for other metrics
            statistics = ["Sum", "Average", "Minimum", "Maximum"]

        return await self._get_cloudwatch_metric_for_accessible_regions(
            Namespace="AWS/ELB",
            MetricName=metric_name,
            Dimensions=[
                {
                    "Name": "LoadBalancerName",
                    "Value": self.raw_data["LoadBalancerName"],
                }
            ],
            StartTime=time_range_start,
            EndTime=time_range_end,
            Period=300,
            Statistics=statistics,
        )
