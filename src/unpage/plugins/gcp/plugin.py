import warnings
from typing import Any

import anyio
import rich
from gcloud.aio import storage as aio_storage
from google.cloud import compute_v1
from googleapiclient import discovery
from pydantic import BaseModel, Field, ValidationError
from pydantic_core import to_jsonable_python

from unpage.config import PluginSettings
from unpage.knowledge import Graph
from unpage.plugins import Plugin
from unpage.plugins.gcp.nodes.base import DEFAULT_GCP_PROJECT_NAME, GcpProject
from unpage.plugins.gcp.nodes.gcp_backend_service import GcpBackendService
from unpage.plugins.gcp.nodes.gcp_compute_instance import GcpComputeInstance
from unpage.plugins.gcp.nodes.gcp_forwarding_rule import GcpForwardingRule
from unpage.plugins.gcp.nodes.gcp_persistent_disk import GcpPersistentDisk
from unpage.plugins.gcp.nodes.gcp_sql_instance import GcpSqlInstance
from unpage.plugins.gcp.nodes.gcp_storage_bucket import GcpStorageBucket
from unpage.plugins.gcp.utils import (
    ensure_gcp_credentials,
    swallow_gcp_client_access_errors,
)
from unpage.plugins.mixins import KnowledgeGraphMixin, McpServerMixin, tool
from unpage.utils import classproperty, confirm, print

warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    message="datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).*",
)


class GcpPluginSettings(BaseModel):
    projects: dict[str, GcpProject] = Field(
        default_factory=lambda: {DEFAULT_GCP_PROJECT_NAME: GcpProject()}
    )

    @property
    def project(self) -> GcpProject:
        return next(iter(self.projects.values()))


class GcpPlugin(Plugin, KnowledgeGraphMixin, McpServerMixin):
    gcp_settings: GcpPluginSettings

    def __init__(
        self, *args: Any, gcp_settings: GcpPluginSettings | None = None, **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self.gcp_settings = gcp_settings if gcp_settings else GcpPluginSettings()

    def init_plugin(self) -> None:
        gcp_projects = self._settings.get("projects")
        if not gcp_projects:
            self.gcp_settings = GcpPluginSettings()
            return
        if not isinstance(gcp_projects, dict):
            raise ValueError("gcp projects must be a dictionary in config.yaml")
        if len(gcp_projects) != 1:
            raise ValueError(
                "More than one GCP project configured in config.yaml; we only support one GCP project at this time. Please let us know if you have more than one gcp project."
            )
        for project_name, project_settings in gcp_projects.items():
            try:
                self.gcp_settings = GcpPluginSettings(
                    projects={
                        project_name: GcpProject(
                            **{"name": project_name, **to_jsonable_python(project_settings)}
                        )
                    }
                )
            except ValidationError as ex:
                raise ValueError(
                    f"Invalid GCP project settings for gcp project '{project_name}'. Review your config.yaml. {project_settings=}; error={ex!s}"
                ) from ex

    async def validate_plugin_config(self) -> None:
        await super().validate_plugin_config()
        ensure_gcp_credentials(self.gcp_settings.project.credentials)

    @classproperty
    def default_plugin_settings(cls) -> PluginSettings:
        return GcpPluginSettings().model_dump()

    async def interactive_configure(self) -> PluginSettings:
        rich.print(
            "> The GCP plugin will add resources from Google Cloud to your infra knowledge graph"
        )
        rich.print("> You can optionally set a GCP project ID and credentials path")
        rich.print(
            "> Specifying no credentials will fallback to using Application Default Credentials"
        )
        rich.print(
            "> Read more about Application Default Credentials at: https://cloud.google.com/docs/authentication/application-default-credentials"
        )
        rich.print("")

        from questionary import text

        project_id = await text(
            "Enter your GCP project ID (leave empty to use default from credentials):",
            default="",
        ).unsafe_ask_async()

        credentials_path = ""
        if await confirm(
            "Would you like to specify a path to a service account key file?",
            default=False,
        ):
            credentials_path = await text(
                "Enter the path to your service account key JSON file:",
                default="",
            ).unsafe_ask_async()

        project_name = project_id if project_id else DEFAULT_GCP_PROJECT_NAME
        settings = GcpPluginSettings(
            projects={
                project_name: GcpProject(
                    name=project_name,
                    project_id=project_id if project_id else None,
                    credentials_path=credentials_path if credentials_path else None,
                )
            }
        )
        return settings.model_dump()

    @property
    def project(self) -> GcpProject:
        return self.gcp_settings.project

    @property
    def project_id(self) -> str:
        return self.project.effective_project_id

    async def populate_graph(self, graph: Graph) -> None:
        ensure_gcp_credentials(self.project.credentials)
        async with anyio.create_task_group() as tg:
            tg.start_soon(self.populate_compute_instances, graph)
            tg.start_soon(self.populate_persistent_disks, graph)
            tg.start_soon(self.populate_sql_instances, graph)
            tg.start_soon(self.populate_storage_buckets, graph)
            tg.start_soon(self.populate_forwarding_rules, graph)
            tg.start_soon(self.populate_backend_services, graph)

    async def populate_compute_instances(self, graph: Graph) -> None:
        """Populate Compute Engine instances from all zones."""
        print("Populating Compute Engine instances")

        instance_count = 0
        async with swallow_gcp_client_access_errors("compute"):
            instances_client = compute_v1.InstancesClient(credentials=self.project.credentials)

            # Get all zones for this project
            zones_client = compute_v1.ZonesClient(credentials=self.project.credentials)
            zones_request = compute_v1.ListZonesRequest(project=self.project_id)
            zones = zones_client.list(request=zones_request)

            for zone in zones:
                # List instances in each zone
                request = compute_v1.ListInstancesRequest(
                    project=self.project_id,
                    zone=zone.name,
                )
                try:
                    instances = instances_client.list(request=request)
                    for instance in instances:
                        # Convert instance to dict
                        instance_dict = compute_v1.Instance.to_dict(instance)
                        await graph.add_node(
                            GcpComputeInstance(
                                node_id=f"projects/{self.project_id}/zones/{zone.name}/instances/{instance.name}",
                                raw_data=instance_dict,
                                _graph=graph,
                                gcp_project=self.project,
                            )
                        )
                        instance_count += 1
                except Exception:
                    # Skip zones we don't have access to
                    pass

        print(f"Initialized {instance_count} Compute Engine instances")

    async def populate_persistent_disks(self, graph: Graph) -> None:
        """Populate persistent disks from all zones."""
        print("Populating persistent disks")

        disk_count = 0
        async with swallow_gcp_client_access_errors("compute"):
            disks_client = compute_v1.DisksClient(credentials=self.project.credentials)

            # Get all zones
            zones_client = compute_v1.ZonesClient(credentials=self.project.credentials)
            zones_request = compute_v1.ListZonesRequest(project=self.project_id)
            zones = zones_client.list(request=zones_request)

            for zone in zones:
                request = compute_v1.ListDisksRequest(
                    project=self.project_id,
                    zone=zone.name,
                )
                try:
                    disks = disks_client.list(request=request)
                    for disk in disks:
                        disk_dict = compute_v1.Disk.to_dict(disk)
                        await graph.add_node(
                            GcpPersistentDisk(
                                node_id=f"projects/{self.project_id}/zones/{zone.name}/disks/{disk.name}",
                                raw_data=disk_dict,
                                _graph=graph,
                                gcp_project=self.project,
                            )
                        )
                        disk_count += 1
                except Exception:
                    pass

        print(f"Initialized {disk_count} persistent disks")

    async def populate_sql_instances(self, graph: Graph) -> None:
        """Populate Cloud SQL instances."""
        print("Populating Cloud SQL instances")

        sql_count = 0
        async with swallow_gcp_client_access_errors("sqladmin"):
            # Use discovery API for Cloud SQL Admin - runs in thread pool since it's synchronous
            try:
                sql_service = await anyio.to_thread.run_sync(
                    lambda: discovery.build(
                        "sqladmin", "v1beta4", credentials=self.project.credentials
                    )
                )

                # List all instances for the project
                request = sql_service.instances().list(project=self.project_id)

                # Handle pagination
                while request is not None:
                    response = await anyio.to_thread.run_sync(request.execute)

                    for instance in response.get("items", []):
                        await graph.add_node(
                            GcpSqlInstance(
                                node_id=f"projects/{self.project_id}/instances/{instance.get('name')}",
                                raw_data=instance,
                                _graph=graph,
                                gcp_project=self.project,
                            )
                        )
                        sql_count += 1

                    # Get next page of results
                    request = sql_service.instances().list_next(
                        previous_request=request, previous_response=response
                    )

            except Exception:
                pass

        print(f"Initialized {sql_count} Cloud SQL instances")

    async def populate_storage_buckets(self, graph: Graph) -> None:
        """Populate Cloud Storage buckets."""
        print("Populating Cloud Storage buckets")

        bucket_count = 0
        async with swallow_gcp_client_access_errors("storage"):
            async with aio_storage.Storage(project=self.project_id) as storage_client:
                try:
                    # List all buckets in the project
                    buckets = await storage_client.list_buckets()

                    # buckets is a dict with 'items' key containing bucket metadata
                    bucket_items = buckets.get("items", [])

                    for bucket_data in bucket_items:
                        # The API returns full bucket metadata
                        bucket_dict = {
                            "id": bucket_data.get("id"),
                            "name": bucket_data.get("name"),
                            "selfLink": bucket_data.get("selfLink"),
                            "location": bucket_data.get("location"),
                            "storageClass": bucket_data.get("storageClass"),
                            "timeCreated": bucket_data.get("timeCreated"),
                            "updated": bucket_data.get("updated"),
                            "projectNumber": bucket_data.get("projectNumber"),
                        }
                        await graph.add_node(
                            GcpStorageBucket(
                                node_id=f"projects/{self.project_id}/buckets/{bucket_data.get('name')}",
                                raw_data=bucket_dict,
                                _graph=graph,
                                gcp_project=self.project,
                            )
                        )
                        bucket_count += 1
                except Exception:
                    pass

        print(f"Initialized {bucket_count} Cloud Storage buckets")

    async def populate_forwarding_rules(self, graph: Graph) -> None:
        """Populate Forwarding Rules (load balancer entry points)."""
        print("Populating Forwarding Rules")

        forwarding_rule_count = 0
        async with swallow_gcp_client_access_errors("compute"):
            # Get global forwarding rules
            forwarding_rules_client = compute_v1.GlobalForwardingRulesClient(
                credentials=self.project.credentials
            )
            try:
                request = compute_v1.ListGlobalForwardingRulesRequest(project=self.project_id)
                global_rules = forwarding_rules_client.list(request=request)

                for rule in global_rules:
                    rule_dict = compute_v1.ForwardingRule.to_dict(rule)
                    await graph.add_node(
                        GcpForwardingRule(
                            node_id=f"projects/{self.project_id}/global/forwardingRules/{rule.name}",
                            raw_data=rule_dict,
                            _graph=graph,
                            gcp_project=self.project,
                        )
                    )
                    forwarding_rule_count += 1
            except Exception:
                pass

            # Get regional forwarding rules
            regions_client = compute_v1.RegionsClient(credentials=self.project.credentials)
            try:
                regions_request = compute_v1.ListRegionsRequest(project=self.project_id)
                regions = regions_client.list(request=regions_request)

                for region in regions:
                    regional_rules_client = compute_v1.ForwardingRulesClient(
                        credentials=self.project.credentials
                    )
                    try:
                        regional_request = compute_v1.ListForwardingRulesRequest(
                            project=self.project_id, region=region.name
                        )
                        regional_rules = regional_rules_client.list(request=regional_request)

                        for rule in regional_rules:
                            rule_dict = compute_v1.ForwardingRule.to_dict(rule)
                            await graph.add_node(
                                GcpForwardingRule(
                                    node_id=f"projects/{self.project_id}/regions/{region.name}/forwardingRules/{rule.name}",
                                    raw_data=rule_dict,
                                    _graph=graph,
                                    gcp_project=self.project,
                                )
                            )
                            forwarding_rule_count += 1
                    except Exception:
                        pass
            except Exception:
                pass

        print(f"Initialized {forwarding_rule_count} Forwarding Rules")

    async def populate_backend_services(self, graph: Graph) -> None:
        """Populate Backend Services."""
        print("Populating Backend Services")

        backend_service_count = 0
        async with swallow_gcp_client_access_errors("compute"):
            # Get global backend services
            backend_services_client = compute_v1.BackendServicesClient(
                credentials=self.project.credentials
            )
            try:
                request = compute_v1.ListBackendServicesRequest(project=self.project_id)
                global_services = backend_services_client.list(request=request)

                for service in global_services:
                    service_dict = compute_v1.BackendService.to_dict(service)
                    await graph.add_node(
                        GcpBackendService(
                            node_id=f"projects/{self.project_id}/global/backendServices/{service.name}",
                            raw_data=service_dict,
                            _graph=graph,
                            gcp_project=self.project,
                        )
                    )
                    backend_service_count += 1
            except Exception:
                pass

            # Get regional backend services
            regions_client = compute_v1.RegionsClient(credentials=self.project.credentials)
            try:
                regions_request = compute_v1.ListRegionsRequest(project=self.project_id)
                regions = regions_client.list(request=regions_request)

                for region in regions:
                    regional_services_client = compute_v1.RegionBackendServicesClient(
                        credentials=self.project.credentials
                    )
                    try:
                        regional_request = compute_v1.ListRegionBackendServicesRequest(
                            project=self.project_id, region=region.name
                        )
                        regional_services = regional_services_client.list(request=regional_request)

                        for service in regional_services:
                            service_dict = compute_v1.BackendService.to_dict(service)
                            await graph.add_node(
                                GcpBackendService(
                                    node_id=f"projects/{self.project_id}/regions/{region.name}/backendServices/{service.name}",
                                    raw_data=service_dict,
                                    _graph=graph,
                                    gcp_project=self.project,
                                )
                            )
                            backend_service_count += 1
                    except Exception:
                        pass
            except Exception:
                pass

        print(f"Initialized {backend_service_count} Backend Services")

    @tool()
    async def get_realtime_instance_status(self, instance_name: str, zone: str) -> dict | str:
        """
        Get real-time status information for a Compute Engine instance directly from GCP API.

        Args:
            instance_name: GCP Compute Engine instance name
            zone: GCP zone where the instance is located

        Returns:
            dict containing current instance state and status details
        """
        async with swallow_gcp_client_access_errors("compute"):
            try:
                instances_client = compute_v1.InstancesClient(credentials=self.project.credentials)
                request = compute_v1.GetInstanceRequest(
                    project=self.project_id,
                    zone=zone,
                    instance=instance_name,
                )
                instance = instances_client.get(request=request)
                return compute_v1.Instance.to_dict(instance)
            except Exception as e:
                return f"Error retrieving instance status: {e!s}"

    @tool()
    async def get_realtime_instance_status_by_node(self, node_id: str) -> dict | str:
        """
        Get real-time status information for a Compute Engine instance node directly from GCP API.

        Args:
            node_id: node ID from the knowledge graph

        Returns:
            dict containing current instance state and status details
        """
        node = await self.context.graph.get_node_safe(node_id)
        if not node:
            return f"Resource with node ID '{node_id}' not found"
        if isinstance(node, GcpComputeInstance):
            zone = node.raw_data.get("zone", "").split("/")[-1]
            instance_name = node.raw_data.get("name")
            if not zone or not instance_name:
                return "Missing zone or instance name in node data"
            return await self.get_realtime_instance_status(instance_name, zone)
        else:
            return f"Node {node_id} is not a Compute Engine instance"
