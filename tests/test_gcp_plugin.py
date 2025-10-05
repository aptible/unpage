"""Basic tests for the GCP plugin."""

from unittest.mock import MagicMock

import pytest

from unpage.knowledge import Graph
from unpage.plugins.gcp import GcpPlugin, GcpPluginSettings
from unpage.plugins.gcp.nodes.base import GcpProject
from unpage.plugins.gcp.nodes.gcp_cloud_function import GcpCloudFunction
from unpage.plugins.gcp.nodes.gcp_cloud_run import GcpCloudRunService
from unpage.plugins.gcp.nodes.gcp_cloud_sql_instance import GcpCloudSqlInstance
from unpage.plugins.gcp.nodes.gcp_compute_instance import GcpComputeInstance
from unpage.plugins.gcp.nodes.gcp_gke_cluster import GcpGkeCluster
from unpage.plugins.gcp.nodes.gcp_load_balancer import (
    GcpBackendService,
    GcpLoadBalancer,
)
from unpage.plugins.gcp.nodes.gcp_persistent_disk import GcpPersistentDisk
from unpage.plugins.gcp.nodes.gcp_storage_bucket import GcpStorageBucket


class TestGcpPlugin:
    """Test the GCP plugin."""

    def test_plugin_registration(self) -> None:
        """Test that the GCP plugin is registered."""
        from unpage.plugins import REGISTRY

        assert "gcp" in REGISTRY
        assert REGISTRY["gcp"] == GcpPlugin

    def test_plugin_name(self) -> None:
        """Test that the plugin name is correct."""
        plugin = GcpPlugin()
        assert plugin.name == "gcp"

    def test_default_settings(self) -> None:
        """Test default plugin settings."""
        settings = GcpPlugin.default_plugin_settings
        assert "projects" in settings
        assert "default" in settings["projects"]
        assert settings["projects"]["default"]["auth_method"] == "adc"

    def test_plugin_initialization(self) -> None:
        """Test plugin initialization with custom settings."""
        settings = GcpPluginSettings(
            projects={
                "test-project": GcpProject(
                    name="test-project",
                    project_id="test-project-123",
                    auth_method="service_account",
                    service_account_key_path="/path/to/key.json",
                    regions=["us-central1", "us-east1"],
                )
            }
        )
        plugin = GcpPlugin(gcp_settings=settings)
        assert len(plugin.gcp_settings.projects) == 1
        assert "test-project" in plugin.gcp_settings.projects
        assert plugin.gcp_settings.projects["test-project"].project_id == "test-project-123"

    @pytest.mark.asyncio
    async def test_compute_instance_node(self) -> None:
        """Test GCP Compute Instance node."""
        mock_graph = MagicMock(spec=Graph)
        mock_project = GcpProject(
            name="test",
            project_id="test-123",
            auth_method="adc",
        )

        instance_data = {
            "id": "123456789",
            "name": "test-instance",
            "status": "RUNNING",
            "machineType": "zones/us-central1-a/machineTypes/e2-micro",
            "zone": "zones/us-central1-a",
            "networkInterfaces": [
                {"networkIP": "10.0.0.1", "accessConfigs": [{"natIP": "34.1.2.3"}]}
            ],
            "disks": [{"source": "projects/test-123/zones/us-central1-a/disks/test-disk"}],
        }

        node = GcpComputeInstance(
            node_id="gcp:compute:instance:123456789",
            raw_data=instance_data,
            _graph=mock_graph,
            gcp_project=mock_project,
        )

        assert node.display_name == "test-instance"
        assert node.status == "RUNNING"
        assert node.machine_type == "e2-micro"
        assert node.zone == "us-central1-a"

        # Test identifiers
        identifiers = await node.get_identifiers()
        assert "123456789" in identifiers
        assert "test-instance" in identifiers
        assert "10.0.0.1" in identifiers
        assert "34.1.2.3" in identifiers

        # Test available metrics
        metrics = await node.list_available_metrics()
        assert "compute.googleapis.com/instance/cpu/utilization" in metrics

    @pytest.mark.asyncio
    async def test_cloud_sql_instance_node(self) -> None:
        """Test GCP Cloud SQL Instance node."""
        mock_graph = MagicMock(spec=Graph)
        mock_project = GcpProject(
            name="test",
            project_id="test-123",
            auth_method="adc",
        )

        sql_data = {
            "name": "test-sql",
            "databaseVersion": "POSTGRES_14",
            "state": "RUNNABLE",
            "region": "us-central1",
            "settings": {
                "tier": "db-f1-micro",
                "dataDiskSizeGb": "10",
                "backupConfiguration": {"enabled": True},
            },
            "ipAddresses": [{"ipAddress": "10.1.2.3"}],
        }

        node = GcpCloudSqlInstance(
            node_id="gcp:sql:instance:test-123:test-sql",
            raw_data=sql_data,
            _graph=mock_graph,
            gcp_project=mock_project,
        )

        assert node.display_name == "test-sql"
        assert node.database_version == "POSTGRES_14"
        assert node.state == "RUNNABLE"
        assert node.region == "us-central1"
        assert node.tier == "db-f1-micro"
        assert node.disk_size_gb == 10
        assert node.backup_enabled is True
        assert node.is_replica is False

        # Test identifiers
        identifiers = await node.get_identifiers()
        assert "test-sql" in identifiers

    @pytest.mark.asyncio
    async def test_storage_bucket_node(self) -> None:
        """Test GCP Storage Bucket node."""
        mock_graph = MagicMock(spec=Graph)
        mock_project = GcpProject(
            name="test",
            project_id="test-123",
            auth_method="adc",
        )

        bucket_data = {
            "id": "test-bucket-123",
            "name": "test-bucket-123",
            "location": "US",
            "storageClass": "STANDARD",
            "versioning": {"enabled": True},
            "lifecycle": {"rule": [{"action": {"type": "Delete"}, "condition": {"age": 30}}]},
        }

        node = GcpStorageBucket(
            node_id="gcp:storage:bucket:test-bucket-123",
            raw_data=bucket_data,
            _graph=mock_graph,
            gcp_project=mock_project,
        )

        assert node.display_name == "test-bucket-123"
        assert node.location == "US"
        assert node.storage_class == "STANDARD"
        assert node.versioning_enabled is True
        assert node.lifecycle_rules_count == 1
        assert node.is_public is False

        # Test available metrics
        metrics = await node.list_available_metrics()
        assert "storage.googleapis.com/storage/object_count" in metrics

    @pytest.mark.asyncio
    async def test_persistent_disk_node(self) -> None:
        """Test GCP Persistent Disk node."""
        mock_graph = MagicMock(spec=Graph)
        mock_project = GcpProject(
            name="test",
            project_id="test-123",
            auth_method="adc",
        )

        disk_data = {
            "id": "987654321",
            "name": "test-disk",
            "status": "READY",
            "sizeGb": "100",
            "type": "zones/us-central1-a/diskTypes/pd-standard",
            "zone": "zones/us-central1-a",
            "users": ["projects/test-123/zones/us-central1-a/instances/test-instance"],
        }

        node = GcpPersistentDisk(
            node_id="gcp:compute:disk:987654321",
            raw_data=disk_data,
            _graph=mock_graph,
            gcp_project=mock_project,
        )

        assert node.display_name == "test-disk"
        assert node.status == "READY"
        assert node.size_gb == 100
        assert node.disk_type == "pd-standard"
        assert node.zone == "us-central1-a"
        assert node.is_attached is True

        # Test references
        refs = await node.get_reference_identifiers()
        ref_ids = [r[0] if isinstance(r, tuple) else r for r in refs]
        assert "test-instance" in ref_ids

    @pytest.mark.asyncio
    async def test_gke_cluster_node(self) -> None:
        """Test GKE Cluster node."""
        mock_graph = MagicMock(spec=Graph)
        mock_project = GcpProject(
            name="test",
            project_id="test-123",
            auth_method="adc",
        )

        cluster_data = {
            "id": "cluster-123",
            "name": "test-cluster",
            "status": "RUNNING",
            "location": "us-central1-a",
            "endpoint": "35.1.2.3",
            "currentMasterVersion": "1.27.3-gke.1200",
            "currentNodeVersion": "1.27.3-gke.1200",
            "currentNodeCount": 3,
            "nodePools": [{"name": "default-pool"}],
        }

        node = GcpGkeCluster(
            node_id="gcp:gke:cluster:test-123:test-cluster",
            raw_data=cluster_data,
            _graph=mock_graph,
            gcp_project=mock_project,
        )

        assert node.display_name == "test-cluster"
        assert node.status == "RUNNING"
        assert node.location == "us-central1-a"
        assert node.cluster_version == "1.27.3-gke.1200"
        assert node.node_count == 3

        # Test available metrics
        metrics = await node.list_available_metrics()
        assert "kubernetes.io/cluster/cpu/allocatable_utilization" in metrics

    @pytest.mark.asyncio
    async def test_cloud_function_node(self) -> None:
        """Test Cloud Function node."""
        mock_graph = MagicMock(spec=Graph)
        mock_project = GcpProject(
            name="test",
            project_id="test-123",
            auth_method="adc",
        )

        function_data = {
            "name": "projects/test-123/locations/us-central1/functions/test-function",
            "status": "ACTIVE",
            "entryPoint": "helloWorld",
            "runtime": "nodejs18",
            "timeout": "60s",
            "availableMemoryMb": 256,
            "httpsTrigger": {
                "url": "https://us-central1-test-123.cloudfunctions.net/test-function"
            },
        }

        node = GcpCloudFunction(
            node_id="gcp:function:v1:test-function",
            raw_data=function_data,
            _graph=mock_graph,
            gcp_project=mock_project,
        )

        assert node.display_name == "test-function"
        assert node.status == "ACTIVE"
        assert node.runtime == "nodejs18"
        assert node.entry_point == "helloWorld"
        assert node.available_memory_mb == 256
        assert node.trigger_type == "HTTPS"
        assert node.is_gen2 is False

        # Test available metrics
        metrics = await node.list_available_metrics()
        assert "cloudfunctions.googleapis.com/function/execution_count" in metrics

    @pytest.mark.asyncio
    async def test_cloud_run_service_node(self) -> None:
        """Test Cloud Run Service node."""
        mock_graph = MagicMock(spec=Graph)
        mock_project = GcpProject(
            name="test",
            project_id="test-123",
            auth_method="adc",
        )

        service_data = {
            "name": "test-service",
            "uid": "service-uid-123",
            "metadata": {
                "name": "test-service",
                "labels": {"cloud.googleapis.com/location": "us-central1"},
                "annotations": {
                    "autoscaling.knative.dev/minScale": "1",
                    "autoscaling.knative.dev/maxScale": "10",
                },
            },
            "spec": {
                "template": {
                    "spec": {
                        "containerConcurrency": 100,
                        "timeoutSeconds": 300,
                        "containers": [
                            {
                                "image": "gcr.io/test-123/my-app:latest",
                                "resources": {"limits": {"cpu": "2", "memory": "1Gi"}},
                            }
                        ],
                    }
                }
            },
            "status": {
                "url": "https://test-service-abc123-uc.a.run.app",
                "latestCreatedRevisionName": "test-service-00001-abc",
                "conditions": [{"type": "Ready", "status": "True"}],
            },
        }

        node = GcpCloudRunService(
            node_id="gcp:run:service:test-service",
            raw_data=service_data,
            _graph=mock_graph,
            gcp_project=mock_project,
        )

        assert node.display_name == "test-service"
        assert node.location == "us-central1"
        assert node.url == "https://test-service-abc123-uc.a.run.app"
        assert node.is_ready is True
        assert node.container_image == "gcr.io/test-123/my-app:latest"
        assert node.min_instances == 1
        assert node.max_instances == 10
        assert node.cpu_limit == "2"
        assert node.memory_limit == "1Gi"

        # Test available metrics
        metrics = await node.list_available_metrics()
        assert "run.googleapis.com/request_count" in metrics

    @pytest.mark.asyncio
    async def test_load_balancer_node(self) -> None:
        """Test Load Balancer node."""
        mock_graph = MagicMock(spec=Graph)
        mock_project = GcpProject(
            name="test",
            project_id="test-123",
            auth_method="adc",
        )

        lb_data = {
            "id": "lb-123",
            "name": "test-load-balancer",
            "kind": "compute#urlMap",
            "selfLink": "https://www.googleapis.com/compute/v1/projects/test-123/global/urlMaps/test-lb",
        }

        node = GcpLoadBalancer(
            node_id="gcp:lb:urlmap:lb-123",
            raw_data=lb_data,
            _graph=mock_graph,
            gcp_project=mock_project,
        )

        assert node.display_name == "test-load-balancer"
        assert node.load_balancer_type == "urlMap"

        # Test available metrics
        metrics = await node.list_available_metrics()
        assert "loadbalancing.googleapis.com/https/request_count" in metrics

    @pytest.mark.asyncio
    async def test_backend_service_node(self) -> None:
        """Test Backend Service node."""
        mock_graph = MagicMock(spec=Graph)
        mock_project = GcpProject(
            name="test",
            project_id="test-123",
            auth_method="adc",
        )

        service_data = {
            "id": "backend-123",
            "name": "test-backend-service",
            "protocol": "HTTPS",
            "loadBalancingScheme": "EXTERNAL",
            "sessionAffinity": "CLIENT_IP",
            "backends": [
                {"group": "projects/test-123/zones/us-central1-a/instanceGroups/test-group"}
            ],
            "healthChecks": ["projects/test-123/global/healthChecks/test-health-check"],
        }

        node = GcpBackendService(
            node_id="gcp:backend:service:backend-123",
            raw_data=service_data,
            _graph=mock_graph,
            gcp_project=mock_project,
        )

        assert node.display_name == "test-backend-service"
        assert node.protocol == "HTTPS"
        assert node.load_balancing_scheme == "EXTERNAL"
        assert node.session_affinity == "CLIENT_IP"

        # Test references
        refs = await node.get_reference_identifiers()
        ref_ids = [r[0] if isinstance(r, tuple) else r for r in refs]
        assert "test-group" in ref_ids
        assert "test-health-check" in ref_ids
