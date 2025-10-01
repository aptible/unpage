from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from unpage.knowledge import Graph
from unpage.plugins.gcp.nodes.base import GcpProject
from unpage.plugins.gcp.plugin import GcpPlugin

if TYPE_CHECKING:
    from fastmcp import Client


@pytest.fixture
def mock_gcp_credentials():
    """Mock GCP credentials."""
    mock_creds = MagicMock()
    mock_creds.valid = True
    return mock_creds


@pytest.fixture
def gcp_plugin(mock_gcp_credentials):
    """Create a GcpPlugin instance with mocked credentials."""
    from unpage.plugins.gcp.plugin import GcpPluginSettings

    with patch("unpage.plugins.gcp.nodes.base.get_default_credentials") as mock_get_creds:
        mock_get_creds.return_value = (mock_gcp_credentials, "test-project-123")

        # Create proper GcpPluginSettings object
        settings = GcpPluginSettings(
            projects={
                "default": GcpProject(
                    name="default",
                    project_id="test-project-123",
                )
            }
        )

        plugin = GcpPlugin(gcp_settings=settings)

        # Pre-cache the credentials to avoid calling get_default_credentials later
        plugin.project._credentials = mock_gcp_credentials

        return plugin


@pytest.mark.asyncio
async def test_populate_compute_instances(gcp_plugin, mock_gcp_credentials):
    """Test populating Compute Engine instances."""
    graph = Graph()

    with patch("unpage.plugins.gcp.plugin.compute_v1.InstancesClient") as mock_instances_client:
        with patch("unpage.plugins.gcp.plugin.compute_v1.ZonesClient") as mock_zones_client:
            # Mock zones
            mock_zone = MagicMock()
            mock_zone.name = "us-central1-a"
            mock_zones_client.return_value.list.return_value = [mock_zone]

            # Mock instance
            mock_instance = MagicMock()
            mock_instance.name = "test-instance"
            mock_instance.id = "123456789"
            mock_instances_client.return_value.list.return_value = [mock_instance]

            # Mock to_dict
            with patch("unpage.plugins.gcp.plugin.compute_v1.Instance.to_dict") as mock_to_dict:
                mock_to_dict.return_value = {
                    "id": "123456789",
                    "name": "test-instance",
                    "zone": "projects/test-project-123/zones/us-central1-a",
                }

                await gcp_plugin.populate_compute_instances(graph)

                # Verify instance was added to graph
                nodes = []
                async for node in graph.iter_nodes():
                    nodes.append(node)

                assert len(nodes) == 1
                assert nodes[0].raw_data["name"] == "test-instance"


@pytest.mark.asyncio
async def test_populate_storage_buckets(gcp_plugin, mock_gcp_credentials):
    """Test populating Cloud Storage buckets."""
    graph = Graph()

    # Also need to patch swallow_gcp_client_access_errors to prevent it from swallowing exceptions
    with patch("unpage.plugins.gcp.plugin.swallow_gcp_client_access_errors"):
        with patch("unpage.plugins.gcp.plugin.aio_storage.Storage") as mock_storage_class:
            # Create async context manager mock properly
            mock_storage_client = AsyncMock()

            # Mock both __aenter__ and __aexit__ for async context manager
            mock_storage_class.return_value.__aenter__ = AsyncMock(return_value=mock_storage_client)
            mock_storage_class.return_value.__aexit__ = AsyncMock(return_value=None)

            # Mock the list_buckets response - gcloud-aio-storage returns a dict with 'items' key
            mock_storage_client.list_buckets = AsyncMock(
                return_value={
                    "items": [
                        {
                            "id": "bucket-123",
                            "name": "test-bucket",
                            "selfLink": "https://storage.googleapis.com/test-bucket",
                            "location": "US",
                            "storageClass": "STANDARD",
                            "timeCreated": "2024-01-01T00:00:00Z",
                        }
                    ]
                }
            )

            await gcp_plugin.populate_storage_buckets(graph)

            # Verify bucket was added to graph
            nodes = []
            async for node in graph.iter_nodes():
                nodes.append(node)

            assert len(nodes) == 1
            assert nodes[0].raw_data["name"] == "test-bucket"


@pytest.mark.asyncio
async def test_get_realtime_instance_status(gcp_plugin, mock_gcp_credentials):
    """Test getting real-time instance status."""
    with patch("unpage.plugins.gcp.plugin.compute_v1.InstancesClient") as mock_client:
        mock_instance = MagicMock()
        mock_instance.name = "test-instance"
        mock_instance.status = "RUNNING"

        mock_client.return_value.get.return_value = mock_instance

        with patch("unpage.plugins.gcp.plugin.compute_v1.Instance.to_dict") as mock_to_dict:
            mock_to_dict.return_value = {
                "name": "test-instance",
                "status": "RUNNING",
            }

            result = await gcp_plugin.get_realtime_instance_status("test-instance", "us-central1-a")

            assert result["name"] == "test-instance"
            assert result["status"] == "RUNNING"


@pytest.mark.asyncio
async def test_populate_sql_instances(gcp_plugin, mock_gcp_credentials):
    """Test populating Cloud SQL instances."""
    graph = Graph()

    with patch("unpage.plugins.gcp.plugin.swallow_gcp_client_access_errors"):
        with patch("unpage.plugins.gcp.plugin.discovery.build") as mock_build:
            with patch("unpage.plugins.gcp.plugin.anyio.to_thread.run_sync") as mock_run_sync:
                # Mock the SQL service
                mock_sql_service = MagicMock()
                mock_instances_resource = MagicMock()
                mock_list_request = MagicMock()

                # Set up the mock chain
                mock_sql_service.instances.return_value = mock_instances_resource
                mock_instances_resource.list.return_value = mock_list_request

                # Mock the response
                mock_response = {
                    "items": [
                        {
                            "name": "test-sql-instance",
                            "databaseVersion": "POSTGRES_14",
                            "state": "RUNNABLE",
                            "connectionName": "project:region:test-sql-instance",
                        }
                    ]
                }

                # Mock list_next to return None (no more pages)
                mock_instances_resource.list_next.return_value = None
                mock_list_request.execute.return_value = mock_response

                # Setup run_sync to execute the callable
                async def mock_run_sync_impl(func):
                    return func()

                mock_run_sync.side_effect = mock_run_sync_impl
                mock_build.return_value = mock_sql_service

                await gcp_plugin.populate_sql_instances(graph)

                # Verify instance was added to graph
                nodes = []
                async for node in graph.iter_nodes():
                    nodes.append(node)

                assert len(nodes) == 1
                assert nodes[0].raw_data["name"] == "test-sql-instance"


@pytest.mark.asyncio
async def test_populate_forwarding_rules(gcp_plugin, mock_gcp_credentials):
    """Test populating Forwarding Rules."""
    graph = Graph()

    with patch("unpage.plugins.gcp.plugin.swallow_gcp_client_access_errors"):
        with patch(
            "unpage.plugins.gcp.plugin.compute_v1.GlobalForwardingRulesClient"
        ) as mock_global_client:
            with patch(
                "unpage.plugins.gcp.plugin.compute_v1.ForwardingRule.to_dict"
            ) as mock_to_dict:
                # Mock global forwarding rules
                mock_rule = MagicMock()
                mock_rule.name = "test-forwarding-rule"

                mock_global_client.return_value.list.return_value = [mock_rule]

                mock_to_dict.return_value = {
                    "name": "test-forwarding-rule",
                    "IPAddress": "34.120.50.100",
                    "target": "projects/test-project/targetHttpProxies/test-proxy",
                }

                await gcp_plugin.populate_forwarding_rules(graph)

                # Verify forwarding rule was added to graph
                nodes = []
                async for node in graph.iter_nodes():
                    nodes.append(node)

                assert len(nodes) == 1
                assert nodes[0].raw_data["name"] == "test-forwarding-rule"


@pytest.mark.asyncio
async def test_populate_backend_services(gcp_plugin, mock_gcp_credentials):
    """Test populating Backend Services."""
    graph = Graph()

    with patch("unpage.plugins.gcp.plugin.swallow_gcp_client_access_errors"):
        with patch(
            "unpage.plugins.gcp.plugin.compute_v1.BackendServicesClient"
        ) as mock_backend_client:
            with patch(
                "unpage.plugins.gcp.plugin.compute_v1.BackendService.to_dict"
            ) as mock_to_dict:
                # Mock backend services
                mock_service = MagicMock()
                mock_service.name = "test-backend-service"

                mock_backend_client.return_value.list.return_value = [mock_service]

                mock_to_dict.return_value = {
                    "name": "test-backend-service",
                    "backends": [
                        {
                            "group": "projects/test-project/zones/us-central1-a/instanceGroups/test-group"
                        }
                    ],
                }

                await gcp_plugin.populate_backend_services(graph)

                # Verify backend service was added to graph
                nodes = []
                async for node in graph.iter_nodes():
                    nodes.append(node)

                assert len(nodes) == 1
                assert nodes[0].raw_data["name"] == "test-backend-service"


@pytest.mark.asyncio
async def test_validate_plugin_config(gcp_plugin, mock_gcp_credentials):
    """Test plugin configuration validation."""
    # Should not raise an exception with valid credentials
    await gcp_plugin.validate_plugin_config()

    # Validation passes when credentials exist and are valid


@pytest.mark.asyncio
async def test_mcp_tools_integration(mcp_client: "Client"):
    """Test GCP plugin tools through MCP server."""
    # This test would require the GCP plugin to be enabled in the test config
    # For now, we'll skip it since we don't have a proper test configuration
    pytest.skip("Requires GCP plugin to be configured in test profile")
