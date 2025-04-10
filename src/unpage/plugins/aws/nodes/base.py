import asyncio
from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING, Any

from aioboto3 import Session
from pydantic import BaseModel, Field

from unpage.knowledge import Node
from unpage.models import Observation
from unpage.plugins.aws.utils import (
    ensure_aws_session,
    list_accessible_regions_for_service,
    swallow_boto_client_access_errors,
)

if TYPE_CHECKING:
    from pydantic import AwareDatetime


CLOUDWATCH_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


DEFAULT_AWS_ACCOUNT_NAME = "default"


class AwsAccount(BaseModel):
    name: str | None = Field(default=DEFAULT_AWS_ACCOUNT_NAME)
    profile: str | None = Field(default=None)

    @property
    def session(self) -> Session:
        if not hasattr(self, "_session"):
            self._session = Session(profile_name=self.profile) if self.profile else Session()
        return self._session


class AwsNode(Node):
    """A base class for all AWS nodes."""

    aws_account: AwsAccount = Field()

    @property
    def session(self) -> Session:
        if not hasattr(self, "_session"):
            self._session = self.aws_account.session
        return self._session

    async def _get_cloudwatch_metric_for_accessible_regions(
        self,
        **cloudwatch_params: Any,
    ) -> list[Observation]:
        await ensure_aws_session(self.session)
        accessible_regions = await list_accessible_regions_for_service(self.session, "cloudwatch")

        # We don't know which region a given resource is in, so check all regions
        # in parallel.
        observation_results = await asyncio.gather(
            *(
                self._get_cloudwatch_metric_for_region(region, **cloudwatch_params)
                for region in accessible_regions
            )
        )

        # Flatten into a list of observations
        observations = []
        [observations.extend(result) for result in observation_results]
        return observations

    async def _get_cloudwatch_metric_for_region(
        self,
        region: str,
        **cloudwatch_params: Any,
    ) -> list[Observation]:
        metric_name = cloudwatch_params.get("MetricName", "UnknownMetric")
        async with (
            swallow_boto_client_access_errors(service_name="cloudwatch", region=region),
            self.session.client("cloudwatch", region_name=region) as client,
        ):
            result = await client.get_metric_statistics(**cloudwatch_params)
            observations: list[Observation] = []
            datapoints: list[dict[str, Any]] = result.get("Datapoints", [])
            if datapoints:
                series: defaultdict[str, dict[AwareDatetime, float]] = defaultdict(dict)

                for point in datapoints:
                    dt = point.get("Timestamp")
                    if not isinstance(dt, datetime):
                        raise ValueError(f"Timestamp is not a datetime: {dt}")

                    # Each point can have multiple values - Average, Minimum,
                    # Maximum, etc. Create a series for each.
                    for key, value in point.items():
                        if key not in ["Timestamp", "Unit"]:
                            series[key][dt] = float(value)

                # Now that we have collected the values for each series,
                # convert them into Observations.
                for key, data in series.items():
                    observations.append(
                        Observation(
                            node_id=self.nid,
                            observation_type=f"{key} {metric_name}",
                            data=data,
                        )
                    )

            return observations
