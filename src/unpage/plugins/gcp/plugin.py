"""Google Cloud Platform plugin for Unpage."""

from typing import TYPE_CHECKING, Any

import anyio
import questionary
import rich
from pydantic import BaseModel, Field, ValidationError
from pydantic_core import to_jsonable_python

from unpage.config import PluginSettings
from unpage.knowledge import Graph
from unpage.plugins import Plugin
from unpage.plugins.gcp.nodes.base import DEFAULT_GCP_PROJECT_NAME, GcpProject

# Import node classes
from unpage.plugins.gcp.nodes.gcp_cloud_function import GcpCloudFunction
from unpage.plugins.gcp.nodes.gcp_cloud_run import GcpCloudRunService
from unpage.plugins.gcp.nodes.gcp_cloud_sql_instance import GcpCloudSqlInstance
from unpage.plugins.gcp.nodes.gcp_compute_instance import GcpComputeInstance
from unpage.plugins.gcp.nodes.gcp_gke_cluster import GcpGkeCluster, GcpGkeNodePool
from unpage.plugins.gcp.nodes.gcp_load_balancer import (
    GcpBackendService,
    GcpLoadBalancer,
    GcpTargetPool,
)
from unpage.plugins.gcp.nodes.gcp_persistent_disk import GcpPersistentDisk
from unpage.plugins.gcp.nodes.gcp_storage_bucket import GcpStorageBucket
from unpage.plugins.gcp.utils import (
    ensure_gcp_credentials,
    get_available_auth_methods,
    get_gcloud_default_project,
    list_accessible_regions_for_service,
    list_gcp_projects,
    paginate_gcp_api,
    swallow_gcp_api_errors,
)
from unpage.plugins.mixins import KnowledgeGraphMixin, McpServerMixin
from unpage.utils import Choice, classproperty, confirm, print, select

if TYPE_CHECKING:
    from google.auth.credentials import Credentials


class GcpPluginSettings(BaseModel):
    """Settings for the GCP plugin."""

    projects: dict[str, GcpProject] = Field(
        default_factory=lambda: {DEFAULT_GCP_PROJECT_NAME: GcpProject()}
    )

    @property
    def project(self) -> GcpProject:
        """Get the first project (for compatibility)."""
        return next(iter(self.projects.values()))


class GcpPlugin(Plugin, KnowledgeGraphMixin, McpServerMixin):
    """Plugin for Google Cloud Platform resources."""

    gcp_settings: GcpPluginSettings

    def __init__(
        self,
        *args: Any,
        gcp_settings: GcpPluginSettings | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.gcp_settings = gcp_settings if gcp_settings else GcpPluginSettings()

    def init_plugin(self) -> None:
        """Initialize plugin from configuration."""
        gcp_projects = self._settings.get("projects")
        if not gcp_projects:
            self.gcp_settings = GcpPluginSettings()
            return

        if not isinstance(gcp_projects, dict):
            raise ValueError("gcp projects must be a dictionary in config.yaml")

        projects_config = {}
        for project_name, project_settings in gcp_projects.items():
            try:
                projects_config[project_name] = GcpProject(
                    **{"name": project_name, **to_jsonable_python(project_settings)}
                )
            except ValidationError as ex:
                raise ValueError(
                    f"Invalid GCP project settings for project '{project_name}'. "
                    f"Review your config.yaml. {project_settings=}; error={ex!s}"
                ) from ex

        self.gcp_settings = GcpPluginSettings(projects=projects_config)

    async def validate_plugin_config(self) -> None:
        """Validate the plugin configuration."""
        await super().validate_plugin_config()

        # Validate credentials for each project
        for project_name, project in self.gcp_settings.projects.items():
            try:
                credentials = project.credentials
                if not await ensure_gcp_credentials(credentials):
                    raise ValueError(f"Invalid credentials for project '{project_name}'")
            except Exception as e:
                raise ValueError(f"Failed to validate project '{project_name}': {e}") from e

    @classproperty
    def default_plugin_settings(cls) -> PluginSettings:
        """Get default plugin settings."""
        return GcpPluginSettings().model_dump()

    async def interactive_configure(self) -> PluginSettings:
        """Interactive configuration for the GCP plugin."""
        rich.print(
            "> The GCP plugin will add resources from Google Cloud Platform to your knowledge graph"
        )
        rich.print(
            "> You can configure multiple GCP projects and choose from different authentication methods"
        )
        rich.print("")

        # Detect available auth methods
        available_auth_methods = get_available_auth_methods()

        # Ask about authentication method
        auth_choices = []
        if "adc" in available_auth_methods:
            auth_choices.append(
                Choice(
                    "adc", "Application Default Credentials (recommended for cloud environments)"
                )
            )
        if "gcloud" in available_auth_methods:
            auth_choices.append(
                Choice("gcloud", "gcloud CLI credentials (recommended for local development)")
            )
        auth_choices.append(Choice("service_account", "Service account key file"))

        selected_auth_method = "adc"  # default
        if auth_choices and await confirm(
            "Would you like to configure authentication for the GCP plugin?", default=True
        ):
            selected_auth_method = await select(
                "Which authentication method would you like to use?",
                choices=auth_choices,
                default=auth_choices[0] if auth_choices else "adc",
            )

        # Get credentials based on selected method
        service_account_key_path = None
        if selected_auth_method == "service_account":
            service_account_key_path = await questionary.text(
                "Enter the path to your service account key file:",
                default="",
            ).unsafe_ask_async()
            if not service_account_key_path:
                rich.print("[red]Service account key path is required for this auth method[/red]")
                return GcpPluginSettings().model_dump()

        # Create a temporary project config to get credentials
        temp_project = GcpProject(
            auth_method=selected_auth_method,
            service_account_key_path=service_account_key_path,
        )

        try:
            credentials = temp_project.get_credentials()
        except Exception as e:
            rich.print(f"[red]Failed to load credentials: {e}[/red]")
            return GcpPluginSettings().model_dump()

        # List available projects
        rich.print("\n> Discovering GCP projects...")
        try:
            available_projects = await list_gcp_projects(credentials)
        except Exception as e:
            rich.print(f"[red]Failed to list GCP projects: {e}[/red]")
            available_projects = []

        # Get default project for gcloud
        default_project_id = None
        if selected_auth_method == "gcloud":
            default_project_id = get_gcloud_default_project()

        # Select projects
        selected_projects = []
        if available_projects:
            if await confirm(
                f"Found {len(available_projects)} projects. Would you like to select projects to include?",
                default=True,
            ):
                # Allow multi-select
                from unpage.utils import checkbox

                project_choices = [
                    Choice(
                        p["projectId"],
                        f"{p['name']} ({p['projectId']})",
                        checked=(p["projectId"] == default_project_id),
                    )
                    for p in available_projects
                ]

                selected_project_ids = await checkbox(
                    "Select the GCP projects to include (use space to select/deselect):",
                    choices=project_choices,
                )

                selected_projects = [
                    p for p in available_projects if p["projectId"] in selected_project_ids
                ]
        else:
            # Manual project entry
            if await confirm("Would you like to manually enter a project ID?", default=True):
                project_id = await questionary.text(
                    "Enter the GCP project ID:",
                    default=default_project_id or "",
                ).unsafe_ask_async()
                if project_id:
                    selected_projects = [
                        {
                            "projectId": project_id,
                            "name": project_id,
                            "projectNumber": "",
                        }
                    ]

        # Ask about region filtering
        region_filter = None
        if selected_projects and await confirm(
            "Would you like to limit scanning to specific regions? (default: all regions)",
            default=False,
        ):
            regions_input = await questionary.text(
                "Enter comma-separated region names (e.g., us-central1,us-east1):",
                default="",
            ).unsafe_ask_async()
            if regions_input:
                region_filter = [r.strip() for r in regions_input.split(",") if r.strip()]

        # Build the settings
        projects_config = {}
        for project in selected_projects:
            project_id = project["projectId"]
            projects_config[project_id] = GcpProject(
                name=project["name"],
                project_id=project_id,
                auth_method=selected_auth_method,
                service_account_key_path=service_account_key_path,
                regions=region_filter,
            )

        # If no projects selected, create a default one
        if not projects_config:
            projects_config[DEFAULT_GCP_PROJECT_NAME] = GcpProject(
                auth_method=selected_auth_method,
                service_account_key_path=service_account_key_path,
            )

        settings = GcpPluginSettings(projects=projects_config)
        return settings.model_dump()

    async def populate_graph(self, graph: Graph) -> None:
        """Populate the knowledge graph with GCP resources."""

        # Process each configured project
        for project_name, project_config in self.gcp_settings.projects.items():
            print(
                f"Populating resources for GCP project: {project_name} ({project_config.project_id})"
            )

            # Ensure credentials are valid
            credentials = project_config.credentials
            if not await ensure_gcp_credentials(credentials):
                print(f"[red]Failed to authenticate for project {project_name}[/red]")
                continue

            # Create tasks for different resource types
            async with anyio.create_task_group() as tg:
                # Core compute and storage
                tg.start_soon(self.populate_compute_instances, graph, project_config)
                tg.start_soon(self.populate_persistent_disks, graph, project_config)
                tg.start_soon(self.populate_cloud_sql_instances, graph, project_config)
                tg.start_soon(self.populate_storage_buckets, graph, project_config)

                # Load balancing
                tg.start_soon(self.populate_load_balancers, graph, project_config)
                tg.start_soon(self.populate_backend_services, graph, project_config)
                tg.start_soon(self.populate_target_pools, graph, project_config)

                # GCP-specific services
                tg.start_soon(self.populate_gke_clusters, graph, project_config)
                tg.start_soon(self.populate_cloud_functions, graph, project_config)
                tg.start_soon(self.populate_cloud_run_services, graph, project_config)

    async def populate_compute_instances(self, graph: Graph, project: GcpProject) -> None:
        """Populate Compute Engine instances."""
        project_id = project.project_id
        if not project_id:
            print(f"No project ID configured for {project.name}")
            return

        credentials = project.credentials

        # Get regions to scan
        regions = project.regions
        if not regions:
            # Get all available regions for compute
            regions = await list_accessible_regions_for_service(project_id, "compute", credentials)

        # Process each region
        for region in regions:
            await self._populate_compute_instances_in_region(graph, project, region)

    async def _populate_compute_instances_in_region(
        self, graph: Graph, project: GcpProject, region: str
    ) -> None:
        """Populate Compute Engine instances in a specific region."""
        project_id = project.project_id
        print(f"Populating Compute Engine instances from {region}")

        instance_count = 0

        # List all zones in the region
        zones_url = (
            f"https://compute.googleapis.com/compute/v1/projects/{project_id}/regions/{region}"
        )

        try:
            zones_data = await self._make_api_request(zones_url, project.credentials)
            zones = [z.split("/")[-1] for z in zones_data.get("zones", [])]
        except Exception:
            # If we can't list zones, try common zone patterns
            zones = [f"{region}-a", f"{region}-b", f"{region}-c"]

        # Get instances from each zone
        for zone in zones:
            url = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/zones/{zone}/instances"

            async with swallow_gcp_api_errors("compute", zone):
                async for instance in paginate_gcp_api(url, project.credentials):
                    await graph.add_node(
                        GcpComputeInstance(
                            node_id=f"gcp:compute:instance:{instance['id']}",
                            raw_data=instance,
                            _graph=graph,
                            gcp_project=project,
                        )
                    )
                    instance_count += 1

        print(f"Initialized {instance_count} Compute Engine instances for {region}")

    async def populate_persistent_disks(self, graph: Graph, project: GcpProject) -> None:
        """Populate Persistent Disks."""
        project_id = project.project_id
        if not project_id:
            print(f"No project ID configured for {project.name}")
            return

        credentials = project.credentials

        # Get regions to scan
        regions = project.regions
        if not regions:
            # Get all available regions for compute
            regions = await list_accessible_regions_for_service(project_id, "compute", credentials)

        # Process each region
        for region in regions:
            await self._populate_persistent_disks_in_region(graph, project, region)

    async def _populate_persistent_disks_in_region(
        self, graph: Graph, project: GcpProject, region: str
    ) -> None:
        """Populate Persistent Disks in a specific region."""
        project_id = project.project_id
        print(f"Populating Persistent Disks from {region}")

        disk_count = 0

        # List all zones in the region (similar to instances)
        zones_url = (
            f"https://compute.googleapis.com/compute/v1/projects/{project_id}/regions/{region}"
        )

        try:
            zones_data = await self._make_api_request(zones_url, project.credentials)
            zones = [z.split("/")[-1] for z in zones_data.get("zones", [])]
        except Exception:
            # If we can't list zones, try common zone patterns
            zones = [f"{region}-a", f"{region}-b", f"{region}-c"]

        # Get disks from each zone
        for zone in zones:
            url = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/zones/{zone}/disks"

            async with swallow_gcp_api_errors("compute", zone):
                async for disk in paginate_gcp_api(url, project.credentials):
                    await graph.add_node(
                        GcpPersistentDisk(
                            node_id=f"gcp:compute:disk:{disk['id']}",
                            raw_data=disk,
                            _graph=graph,
                            gcp_project=project,
                        )
                    )
                    disk_count += 1

        print(f"Initialized {disk_count} Persistent Disks for {region}")

    async def populate_cloud_sql_instances(self, graph: Graph, project: GcpProject) -> None:
        """Populate Cloud SQL instances."""
        project_id = project.project_id
        if not project_id:
            print(f"No project ID configured for {project.name}")
            return

        print(f"Populating Cloud SQL instances for project {project_id}")

        instance_count = 0
        url = f"https://sqladmin.googleapis.com/v1/projects/{project_id}/instances"

        async with swallow_gcp_api_errors("sqladmin", None):
            async for instance in paginate_gcp_api(url, project.credentials):
                await graph.add_node(
                    GcpCloudSqlInstance(
                        node_id=f"gcp:sql:instance:{project_id}:{instance['name']}",
                        raw_data=instance,
                        _graph=graph,
                        gcp_project=project,
                    )
                )
                instance_count += 1

        print(f"Initialized {instance_count} Cloud SQL instances")

    async def populate_storage_buckets(self, graph: Graph, project: GcpProject) -> None:
        """Populate Cloud Storage buckets."""
        project_id = project.project_id
        if not project_id:
            print(f"No project ID configured for {project.name}")
            return

        print(f"Populating Cloud Storage buckets for project {project_id}")

        bucket_count = 0
        url = f"https://storage.googleapis.com/storage/v1/b?project={project_id}"

        async with swallow_gcp_api_errors("storage", None):
            async for bucket in paginate_gcp_api(url, project.credentials, items_key="items"):
                # Get additional bucket details if needed
                bucket_name = bucket.get("name")
                if bucket_name:
                    # Optionally fetch detailed bucket info
                    detail_url = f"https://storage.googleapis.com/storage/v1/b/{bucket_name}"
                    try:
                        detailed_bucket = await self._make_api_request(
                            detail_url, project.credentials
                        )
                        bucket.update(detailed_bucket)
                    except Exception as ex:
                        print(f"Failed to fetch storage bucket '{bucket}': {ex}")
                        pass

                await graph.add_node(
                    GcpStorageBucket(
                        node_id=f"gcp:storage:bucket:{bucket.get('id', bucket.get('name'))}",
                        raw_data=bucket,
                        _graph=graph,
                        gcp_project=project,
                    )
                )
                bucket_count += 1

        print(f"Initialized {bucket_count} Cloud Storage buckets")

    async def populate_load_balancers(self, graph: Graph, project: GcpProject) -> None:
        """Populate HTTP(S) Load Balancers."""
        project_id = project.project_id
        if not project_id:
            print(f"No project ID configured for {project.name}")
            return

        print(f"Populating Load Balancers for project {project_id}")

        lb_count = 0
        # Global load balancers (URL maps as proxy for load balancers)
        url = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/global/urlMaps"

        async with swallow_gcp_api_errors("compute", None):
            async for url_map in paginate_gcp_api(url, project.credentials):
                await graph.add_node(
                    GcpLoadBalancer(
                        node_id=f"gcp:lb:urlmap:{url_map['id']}",
                        raw_data=url_map,
                        _graph=graph,
                        gcp_project=project,
                    )
                )
                lb_count += 1

        print(f"Initialized {lb_count} Load Balancers")

    async def populate_backend_services(self, graph: Graph, project: GcpProject) -> None:
        """Populate Backend Services."""
        project_id = project.project_id
        if not project_id:
            print(f"No project ID configured for {project.name}")
            return

        print(f"Populating Backend Services for project {project_id}")

        service_count = 0
        # Global backend services
        url = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/global/backendServices"

        async with swallow_gcp_api_errors("compute", None):
            async for service in paginate_gcp_api(url, project.credentials):
                await graph.add_node(
                    GcpBackendService(
                        node_id=f"gcp:backend:service:{service['id']}",
                        raw_data=service,
                        _graph=graph,
                        gcp_project=project,
                    )
                )
                service_count += 1

        # Regional backend services
        regions = project.regions
        if not regions:
            regions = await list_accessible_regions_for_service(
                project_id, "compute", project.credentials
            )

        for region in regions:
            regional_url = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/regions/{region}/backendServices"
            async with swallow_gcp_api_errors("compute", region):
                async for service in paginate_gcp_api(regional_url, project.credentials):
                    await graph.add_node(
                        GcpBackendService(
                            node_id=f"gcp:backend:service:{service['id']}",
                            raw_data=service,
                            _graph=graph,
                            gcp_project=project,
                        )
                    )
                    service_count += 1

        print(f"Initialized {service_count} Backend Services")

    async def populate_target_pools(self, graph: Graph, project: GcpProject) -> None:
        """Populate Target Pools (for Network Load Balancers)."""
        project_id = project.project_id
        if not project_id:
            print(f"No project ID configured for {project.name}")
            return

        print(f"Populating Target Pools for project {project_id}")

        pool_count = 0
        # Target pools are regional
        regions = project.regions
        if not regions:
            regions = await list_accessible_regions_for_service(
                project_id, "compute", project.credentials
            )

        for region in regions:
            url = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/regions/{region}/targetPools"
            async with swallow_gcp_api_errors("compute", region):
                async for pool in paginate_gcp_api(url, project.credentials):
                    await graph.add_node(
                        GcpTargetPool(
                            node_id=f"gcp:lb:targetpool:{pool['id']}",
                            raw_data=pool,
                            _graph=graph,
                            gcp_project=project,
                        )
                    )
                    pool_count += 1

        print(f"Initialized {pool_count} Target Pools")

    async def populate_gke_clusters(self, graph: Graph, project: GcpProject) -> None:
        """Populate GKE clusters."""
        project_id = project.project_id
        if not project_id:
            print(f"No project ID configured for {project.name}")
            return

        print(f"Populating GKE clusters for project {project_id}")

        cluster_count = 0
        node_pool_count = 0

        # GKE clusters can be zonal or regional
        # We'll list all clusters at the project level
        url = f"https://container.googleapis.com/v1/projects/{project_id}/locations/-/clusters"

        async with swallow_gcp_api_errors("container", None):
            response = await self._make_api_request(url, project.credentials)
            clusters = response.get("clusters", [])

            for cluster in clusters:
                # Add the cluster
                await graph.add_node(
                    GcpGkeCluster(
                        node_id=f"gcp:gke:cluster:{project_id}:{cluster['name']}",
                        raw_data=cluster,
                        _graph=graph,
                        gcp_project=project,
                    )
                )
                cluster_count += 1

                # Add node pools
                for node_pool in cluster.get("nodePools", []):
                    # Add cluster info to node pool data
                    node_pool["cluster_name"] = cluster["name"]
                    node_pool["location"] = cluster.get("location", "")

                    await graph.add_node(
                        GcpGkeNodePool(
                            node_id=f"gcp:gke:nodepool:{project_id}:{cluster['name']}:{node_pool['name']}",
                            raw_data=node_pool,
                            _graph=graph,
                            gcp_project=project,
                        )
                    )
                    node_pool_count += 1

        print(f"Initialized {cluster_count} GKE clusters with {node_pool_count} node pools")

    async def populate_cloud_functions(self, graph: Graph, project: GcpProject) -> None:
        """Populate Cloud Functions (v1 and v2)."""
        project_id = project.project_id
        if not project_id:
            print(f"No project ID configured for {project.name}")
            return

        print(f"Populating Cloud Functions for project {project_id}")

        function_count = 0

        # Try v2 functions first
        v2_url = (
            f"https://cloudfunctions.googleapis.com/v2/projects/{project_id}/locations/-/functions"
        )

        async with swallow_gcp_api_errors("cloudfunctions", None):
            async for function in paginate_gcp_api(
                v2_url, project.credentials, items_key="functions"
            ):
                await graph.add_node(
                    GcpCloudFunction(
                        node_id=f"gcp:function:v2:{function['name'].split('/')[-1]}",
                        raw_data=function,
                        _graph=graph,
                        gcp_project=project,
                    )
                )
                function_count += 1

        # Also try v1 functions
        v1_url = (
            f"https://cloudfunctions.googleapis.com/v1/projects/{project_id}/locations/-/functions"
        )

        async with swallow_gcp_api_errors("cloudfunctions", None):
            async for function in paginate_gcp_api(
                v1_url, project.credentials, items_key="functions"
            ):
                # Skip if we already have this function from v2
                function_name = function["name"].split("/")[-1]
                node_id = f"gcp:function:v1:{function_name}"

                # Check if we already added this as v2
                # Skip duplicate check for now (would need graph API to check existing nodes)
                await graph.add_node(
                    GcpCloudFunction(
                        node_id=node_id,
                        raw_data=function,
                        _graph=graph,
                        gcp_project=project,
                    )
                )
                function_count += 1

        print(f"Initialized {function_count} Cloud Functions")

    async def populate_cloud_run_services(self, graph: Graph, project: GcpProject) -> None:
        """Populate Cloud Run services."""
        project_id = project.project_id
        if not project_id:
            print(f"No project ID configured for {project.name}")
            return

        print(f"Populating Cloud Run services for project {project_id}")

        service_count = 0

        # Cloud Run services are regional, but we can list all at once
        url = f"https://run.googleapis.com/v2/projects/{project_id}/locations/-/services"

        async with swallow_gcp_api_errors("run", None):
            async for service in paginate_gcp_api(url, project.credentials, items_key="services"):
                await graph.add_node(
                    GcpCloudRunService(
                        node_id=f"gcp:run:service:{service['name'].split('/')[-1]}",
                        raw_data=service,
                        _graph=graph,
                        gcp_project=project,
                    )
                )
                service_count += 1

        print(f"Initialized {service_count} Cloud Run services")

    async def _make_api_request(self, url: str, credentials: "Credentials") -> dict:
        """Make an API request with the given credentials."""
        if not credentials.valid:
            from google.auth.transport import requests as google_requests

            request = google_requests.Request()
            credentials.refresh(request)

        token = credentials.token
        headers = {"Authorization": f"Bearer {token}"}

        import aiohttp

        async with (
            aiohttp.ClientSession() as session,
            session.get(url, headers=headers) as response,
        ):
            if response.status >= 400:
                error_text = await response.text()
                raise Exception(f"GCP API error ({response.status}): {error_text}")
            return await response.json()
