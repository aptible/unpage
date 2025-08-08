import warnings
from collections.abc import AsyncGenerator
from typing import Literal

import anyio
import boto3.session
import rich
from aioboto3 import Session
from pydantic import BaseModel, Field, ValidationError
from pydantic_core import to_jsonable_python

from unpage.config.utils import PluginSettings
from unpage.knowledge import Graph
from unpage.plugins import Plugin
from unpage.plugins.aptible.nodes.aptible_aws_instance import AptibleAwsInstance
from unpage.plugins.aws.nodes.aws_alb_target_group import AwsAlbTargetGroup
from unpage.plugins.aws.nodes.aws_application_load_balancer import (
    AwsApplicationLoadBalancer,
)
from unpage.plugins.aws.nodes.aws_classic_load_balancer import AwsClassicLoadBalancer
from unpage.plugins.aws.nodes.aws_ebs_volume import AwsEbsVolume
from unpage.plugins.aws.nodes.aws_ec2_instance import AwsEc2Instance
from unpage.plugins.aws.nodes.aws_rds_database import AwsRdsDatabase
from unpage.plugins.aws.nodes.aws_s3_bucket import AwsS3Bucket
from unpage.plugins.aws.nodes.base import DEFAULT_AWS_ACCOUNT_NAME, AwsAccount
from unpage.plugins.aws.utils import (
    ensure_aws_session,
    list_accessible_regions_for_service,
    swallow_boto_client_access_errors,
)
from unpage.plugins.mixins import KnowledgeGraphMixin, McpServerMixin, tool
from unpage.utils import Choice, confirm, print, select

warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    message="datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).*",
)


class AwsPluginSettings(BaseModel):
    accounts: dict[str, AwsAccount] = Field(
        default_factory=lambda: {DEFAULT_AWS_ACCOUNT_NAME: AwsAccount()}
    )

    @property
    def account(self) -> AwsAccount:
        return next(iter(self.accounts.values()))


class AwsPlugin(Plugin, KnowledgeGraphMixin, McpServerMixin):
    aws_settings: AwsPluginSettings = Field(default_factory=AwsPluginSettings)

    def init_plugin(self) -> None:
        aws_accounts = self._settings.get("accounts")
        if not aws_accounts:
            self.aws_settings = AwsPluginSettings()
            return
        if not isinstance(aws_accounts, dict):
            raise ValueError("aws accounts must be a dictionary in config.yaml")
        if len(aws_accounts) != 1:
            raise ValueError(
                "More than one AWS account configured in config.yaml; we only support one AWS account at this time. Please let us know if you have more than one aws account."
            )
        for account_name, account_settings in aws_accounts.items():
            try:
                self.aws_settings = AwsPluginSettings(
                    accounts={
                        account_name: AwsAccount(
                            **{"name": account_name, **to_jsonable_python(account_settings)}
                        )
                    }
                )
            except ValidationError as ex:
                raise ValueError(
                    f"Invalid AWS account settings for aws account '{account_name}'. Review your config.yaml. {account_settings=}; error={ex!s}"
                ) from ex

    async def validate_plugin_config(self) -> None:
        await super().validate_plugin_config()
        await ensure_aws_session(self.session)

    async def interactive_configure(self) -> PluginSettings:
        rich.print("> The AWS plugin will add resources from AWS to your infra knowledge graph")
        rich.print(
            "> You can optionally set an AWS profile from your system that Unpage will use to authenticate AWS requests"
        )
        rich.print(
            "> Specifying no profile will fallback to using the standard AWS credential providers"
        )
        rich.print(
            "> Read more about the standard credential providers at: https://docs.aws.amazon.com/sdkref/latest/guide/standardized-credentials.html"
        )
        rich.print("")
        avail_aws_profiles = boto3.session.Session().available_profiles
        selected_aws_profile: list[str] = []
        if avail_aws_profiles and await confirm(
            "Would you like to select an AWS profile for Unpage to use when querying your AWS infrastructure?",
            default=True,
        ):
            enable_search = len(avail_aws_profiles) > 10
            choices = [
                Choice(p, checked=(p == self.aws_settings.account.profile))
                for p in avail_aws_profiles
            ]
            checked_choices = [c for c in choices if c.checked]
            default_choice = choices[0] if not checked_choices else checked_choices[0]
            selected_aws_profile = [
                await select(
                    "Which AWS profile would you like to use with the Unpage MCP Server?",
                    choices=choices,
                    default=default_choice,
                    use_search_filter=enable_search,
                    use_jk_keys=not enable_search,
                )
            ]
        settings = AwsPluginSettings(
            accounts={
                profile_name: AwsAccount(
                    name=profile_name,
                    profile=profile_name,
                )
                for profile_name in selected_aws_profile
            }
        )
        return settings.model_dump()

    @property
    def session(self) -> Session:
        if not hasattr(self, "_session"):
            self._session = self.aws_settings.account.session
        return self._session

    async def populate_graph(self, graph: Graph) -> None:
        await ensure_aws_session(self.session)
        async with anyio.create_task_group() as tg:
            tg.start_soon(self.populate_rds_databases, graph)
            tg.start_soon(self.populate_ec2_instances, graph)
            tg.start_soon(self.populate_classic_load_balancers, graph)
            tg.start_soon(self.populate_application_load_balancers, graph)
            tg.start_soon(self.populate_alb_target_groups, graph)
            tg.start_soon(self.populate_ebs_volumes, graph)
            tg.start_soon(self.populate_s3_buckets, graph)

    async def populate_rds_databases(self, graph: Graph) -> None:
        async with anyio.create_task_group() as tg:
            for region in await list_accessible_regions_for_service(self.session, "rds"):
                tg.start_soon(self._populate_rds_databases_in_region, graph, region)

    async def _populate_rds_databases_in_region(self, graph: Graph, region: str) -> None:
        print(f"Populating RDS databases from {region}")

        rds_database_count = 0
        async for page in self._paginate("rds", "describe_db_instances", region):
            for instance in page["DBInstances"]:
                await graph.add_node(
                    AwsRdsDatabase(
                        node_id=instance["DBInstanceArn"],
                        raw_data=instance,
                        _graph=graph,
                        aws_account=self.aws_settings.account,
                    )
                )
                rds_database_count += 1

        print(f"Initialized {rds_database_count} RDS databases for {region}")

    async def populate_ec2_instances(self, graph: Graph) -> None:
        async with anyio.create_task_group() as tg:
            for region in await list_accessible_regions_for_service(self.session, "ec2"):
                tg.start_soon(self._populate_ec2_instances_in_region, graph, region)

    async def _populate_ec2_instances_in_region(self, graph: Graph, region: str) -> None:
        print(f"Populating EC2 instances from {region}")

        ec2_instance_count = 0
        async for page in self._paginate("ec2", "describe_instances", region):
            for reservation in page["Reservations"]:
                for instance in reservation["Instances"]:
                    await graph.add_node(
                        AwsEc2Instance(
                            node_id=instance["InstanceId"],
                            raw_data=instance,
                            _graph=graph,
                            aws_account=self.aws_settings.account,
                        )
                    )
                    ec2_instance_count += 1

        print(f"Initialized {ec2_instance_count} EC2 instances for {region}")

    async def populate_classic_load_balancers(self, graph: Graph) -> None:
        async with anyio.create_task_group() as tg:
            for region in await list_accessible_regions_for_service(self.session, "elb"):
                tg.start_soon(self._populate_classic_load_balancers_in_region, graph, region)

    async def _populate_classic_load_balancers_in_region(self, graph: Graph, region: str) -> None:
        print(f"Populating classic load balancers from {region}")

        elb_count = 0
        async for page in self._paginate("elb", "describe_load_balancers", region):
            for balancer in page["LoadBalancerDescriptions"]:
                await graph.add_node(
                    AwsClassicLoadBalancer(
                        node_id=balancer["LoadBalancerName"],
                        raw_data=balancer,
                        _graph=graph,
                        aws_account=self.aws_settings.account,
                    )
                )
                elb_count += 1

        print(f"Initialized {elb_count} classic load balancers for {region}")

    async def populate_application_load_balancers(self, graph: Graph) -> None:
        async with anyio.create_task_group() as tg:
            for region in await list_accessible_regions_for_service(self.session, "elbv2"):
                tg.start_soon(self._populate_application_load_balancers_in_region, graph, region)

    async def _populate_application_load_balancers_in_region(
        self, graph: Graph, region: str
    ) -> None:
        print(f"Populating application load balancers from {region}")

        alb_count = 0
        async for page in self._paginate("elbv2", "describe_load_balancers", region):
            for balancer in page["LoadBalancers"]:
                await graph.add_node(
                    AwsApplicationLoadBalancer(
                        node_id=balancer["LoadBalancerArn"],
                        raw_data=balancer,
                        _graph=graph,
                        aws_account=self.aws_settings.account,
                    )
                )
                alb_count += 1

        print(f"Initialized {alb_count} application load balancers for {region}")

    async def populate_alb_target_groups(self, graph: Graph) -> None:
        async with anyio.create_task_group() as tg:
            for region in await list_accessible_regions_for_service(self.session, "elbv2"):
                tg.start_soon(self._populate_alb_target_groups_in_region, graph, region)

    async def _populate_alb_target_groups_in_region(self, graph: Graph, region: str) -> None:
        print(f"Populating ALB target groups from {region}")

        alb_target_group_count = 0
        async for page in self._paginate("elbv2", "describe_target_groups", region):
            for target_group in page["TargetGroups"]:
                await graph.add_node(
                    AwsAlbTargetGroup(
                        node_id=target_group["TargetGroupArn"],
                        raw_data=target_group,
                        _graph=graph,
                        aws_account=self.aws_settings.account,
                    )
                )
                alb_target_group_count += 1

        print(f"Initialized {alb_target_group_count} ALB target groups for {region}")

    async def populate_ebs_volumes(self, graph: Graph) -> None:
        async with anyio.create_task_group() as tg:
            for region in await list_accessible_regions_for_service(self.session, "ec2"):
                tg.start_soon(self._populate_ebs_volumes_in_region, graph, region)

    async def _populate_ebs_volumes_in_region(self, graph: Graph, region: str) -> None:
        print(f"Populating EBS volumes from {region}")

        ebs_volume_count = 0
        async for page in self._paginate("ec2", "describe_volumes", region):
            for volume in page["Volumes"]:
                await graph.add_node(
                    AwsEbsVolume(
                        node_id=volume["VolumeId"],
                        raw_data=volume,
                        _graph=graph,
                        aws_account=self.aws_settings.account,
                    )
                )
                ebs_volume_count += 1

        print(f"Initialized {ebs_volume_count} EBS volumes for {region}")

    async def populate_s3_buckets(self, graph: Graph) -> None:
        # S3 buckets are global resources, not regional like other AWS services
        # We only need to call list_buckets once, not per region
        print("Populating S3 buckets")

        s3_bucket_count = 0
        async with (
            swallow_boto_client_access_errors(service_name="s3", region="us-east-1"),
            self.session.client("s3", region_name="us-east-1") as client,
        ):
            paginator = client.get_paginator("list_buckets")
            async for page in paginator.paginate():
                for bucket in page["Buckets"]:
                    await graph.add_node(
                        AwsS3Bucket(
                            node_id=bucket["Name"],
                            raw_data=bucket,
                            _graph=graph,
                            aws_account=self.aws_settings.account,
                        )
                    )
                    s3_bucket_count += 1

        print(f"Initialized {s3_bucket_count} S3 buckets")

    @tool()
    async def get_realtime_instance_status(self, instance_id: str, region: str) -> dict | str:
        """
        Get real-time status information for an EC2 instance directly from AWS API.

        Args:
            instance_id: Optional AWS EC2 instance ID
            region: AWS region where the instance is located

        Returns:
            dict containing current instance state and status details
        """
        async with (
            swallow_boto_client_access_errors(service_name="ec2", region=region),
            self.session.client("ec2", region_name=region) as client,
        ):
            try:
                response = await client.describe_instance_status(InstanceIds=[instance_id])
                if not response["InstanceStatuses"]:
                    return f"No instance found with ID '{instance_id}' in region '{region}'"
                return response["InstanceStatuses"][0]
            except Exception as e:
                return f"Error retrieving instance status: {e!s}"

    @tool()
    async def get_realtime_instance_status_by_node(self, node_id: str) -> dict | str:
        """
        Get real-time status information for an EC2 instance node directly from AWS API.

        Args:
            node_id: node ID from the knowledge graph

        Returns:
            dict containing current instance state and status details
        """
        node = await self.context.graph.get_node_safe(node_id)
        if not node:
            return f"Resource with node ID '{node_id}' not found"
        if isinstance(node, AwsEc2Instance):
            return await self.get_realtime_instance_status(
                node.raw_data["InstanceId"], node.raw_data["Placement"]["AvailabilityZone"][:-1]
            )
        elif isinstance(node, AptibleAwsInstance) and "instance_id" in node.raw_data:
            return await self.get_realtime_instance_status(
                node.raw_data["instance_id"], node.raw_data["availability_zone"][:-1]
            )
        else:
            return f"Node {node_id} is not an EC2 instance or does not have an instance ID"

    async def _paginate(
        self,
        service_name: Literal["ec2", "elb", "elbv2", "rds"],
        action: str,
        region: str,
    ) -> AsyncGenerator[dict, None]:
        async with (
            swallow_boto_client_access_errors(service_name=service_name, region=region),
            self.session.client(service_name, region_name=region) as client,
        ):
            paginator = client.get_paginator(action)
            async for page in paginator.paginate():
                yield page
