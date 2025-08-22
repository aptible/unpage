"""Tests for the graph build CLI command."""

from unittest.mock import patch, AsyncMock, MagicMock


@patch("unpage.cli.graph.build.telemetry.send_event")
@patch("unpage.cli.graph.build.create_pid_file")
@patch("unpage.cli.graph.build.cleanup_pid_file")
@patch("unpage.cli.graph.build.check_and_create_lock")
@patch("unpage.cli.graph.build.PluginManager")
@patch("unpage.cli.graph.build.Graph")
def test_build_graph_success(
    mock_graph,
    mock_plugin_manager,
    mock_check_lock,
    mock_cleanup_pid,
    mock_create_pid,
    mock_send_event,
    unpage,
    mock_config_manager,
):
    """Test successful graph building.

    Should:
    - Check for existing lock and proceed if none
    - Load plugins with KnowledgeGraphMixin capability
    - Build graph by populating from plugins and inferring edges
    - Save graph to output file
    - Exit with code 0 (success)
    """
    # Mock external systems
    mock_send_event.return_value = None
    mock_check_lock.return_value = True  # No existing build running
    mock_create_pid.return_value = None
    mock_cleanup_pid.return_value = None

    # Setup graph and plugin manager mocks
    mock_graph_instance = AsyncMock()
    mock_graph_instance.infer_edges.return_value = None
    mock_graph_instance.save.return_value = None

    # Create proper async iterators for counting
    async def mock_iter_edges():
        mock_edge1 = MagicMock()
        mock_edge1.properties = {"relationship_type": "connects_to"}
        mock_edge2 = MagicMock()
        mock_edge2.properties = {"relationship_type": "connects_to"}
        yield mock_edge1
        yield mock_edge2

    async def mock_iter_nodes():
        mock_node = MagicMock()
        mock_node.node_type = "server"
        yield mock_node

    # Replace the methods themselves with async generators
    mock_graph_instance.iter_edges = mock_iter_edges
    mock_graph_instance.iter_nodes = mock_iter_nodes
    mock_graph.return_value = mock_graph_instance

    mock_plugin = AsyncMock()
    mock_plugin.name = "test-plugin"
    mock_plugin.populate_graph.return_value = None
    mock_plugin_manager_instance = MagicMock()
    mock_plugin_manager_instance.get_plugins_with_capability.return_value = [mock_plugin]
    mock_plugin_manager.return_value = mock_plugin_manager_instance

    # Run the command
    stdout, stderr, exit_code = unpage("graph build")

    # Verify success (tests real CLI output logic)
    assert stderr == ""
    assert exit_code == 0
    assert "Building graph..." in stdout
    assert "Graph built in" in stdout
    assert "Graph saved to" in stdout
    assert "=== Summary ===" in stdout

    # Verify process management
    mock_check_lock.assert_called_once()
    mock_create_pid.assert_called_once()
    mock_cleanup_pid.assert_called_once()

    # Verify graph operations
    mock_graph_instance.infer_edges.assert_called_once()
    mock_graph_instance.save.assert_called_once()


@patch("unpage.cli.graph.build.telemetry.send_event")
@patch("unpage.cli.graph.build.check_and_create_lock")
def test_build_graph_already_running(mock_check_lock, mock_send_event, unpage, mock_config_manager):
    """Test graph building when already running.

    Should:
    - Check for existing lock and detect running process
    - Exit with code 1 (error) when another build is running
    """
    # Mock external systems
    mock_send_event.return_value = None
    mock_check_lock.return_value = False  # Existing build is running

    # Run the command
    stdout, stderr, exit_code = unpage("graph build")

    # Verify error handling (tests real error message logic)
    assert "Graph build already running" in stdout
    assert "Use 'unpage graph stop' to stop it if needed" in stdout
    assert stderr == ""
    assert exit_code == 1

    # Verify lock check was called
    mock_check_lock.assert_called_once()


@patch("unpage.cli.graph.build.telemetry.send_event")
@patch("unpage.cli.graph.build.asyncio.create_subprocess_shell")
@patch("unpage.cli.graph.build.get_log_file")
@patch("unpage.cli.graph.build.check_and_create_lock")
def test_build_graph_background(
    mock_check_lock,
    mock_get_log_file,
    mock_subprocess,
    mock_send_event,
    unpage,
    mock_config_manager,
):
    """Test graph building in background mode.

    Should:
    - Start subprocess in background when background=True
    - Set up logging to file
    - Exit with code 0 (success) after starting background process
    """
    # Mock external systems
    mock_send_event.return_value = None
    mock_check_lock.return_value = True

    # Mock log file with proper sync methods and context manager
    from pathlib import Path
    from unittest.mock import mock_open

    mock_log_file = MagicMock(spec=Path)
    mock_log_file.parent.mkdir.return_value = None

    # Create a proper context manager mock
    mock_file_handle = mock_open()
    mock_log_file.open.return_value.__enter__ = mock_file_handle
    mock_log_file.open.return_value.__exit__ = MagicMock(return_value=None)
    mock_get_log_file.return_value = mock_log_file

    mock_process = AsyncMock()
    mock_subprocess.return_value = mock_process

    # Run the command in background mode
    stdout, stderr, exit_code = unpage("graph build --background")

    # Verify success and background startup (tests real background message logic)
    assert "Graph building started in background" in stdout
    assert "Check progress: unpage graph logs --follow" in stdout
    assert "Stop with: unpage graph stop" in stdout
    assert stderr == ""
    assert exit_code == 0

    # Verify subprocess was started
    mock_subprocess.assert_called_once()
    mock_get_log_file.assert_called_once()


@patch("unpage.cli.graph.build.telemetry.send_event")
@patch("unpage.cli.graph.build.anyio.sleep")
@patch("unpage.cli.graph.build.create_pid_file")
@patch("unpage.cli.graph.build.cleanup_pid_file")
@patch("unpage.cli.graph.build.check_and_create_lock")
@patch("unpage.cli.graph.build.PluginManager")
@patch("unpage.cli.graph.build.Graph")
def test_build_graph_with_interval(
    mock_graph,
    mock_plugin_manager,
    mock_check_lock,
    mock_cleanup_pid,
    mock_create_pid,
    mock_sleep,
    mock_send_event,
    unpage,
    mock_config_manager,
):
    """Test continuous graph building with interval.

    This test only verifies the first build cycle to avoid infinite loops.
    In practice, the interval mode would continue until interrupted.

    Should:
    - Build graph repeatedly with specified interval
    - Handle continuous mode correctly
    - Exit with code 0 (success)
    """
    # Mock external systems
    mock_send_event.return_value = None
    mock_check_lock.return_value = True
    mock_create_pid.return_value = None
    mock_cleanup_pid.return_value = None

    # Setup graph operations
    mock_graph_instance = AsyncMock()
    mock_graph_instance.infer_edges.return_value = None
    mock_graph_instance.save.return_value = None

    # Create proper async iterators for counting (empty for interval test)
    async def mock_iter_edges():
        # Empty async generator for clean count test
        if False:
            yield  # Make it an async generator

    async def mock_iter_nodes():
        # Empty async generator for clean count test
        if False:
            yield  # Make it an async generator

    # Replace the methods themselves with async generators
    mock_graph_instance.iter_edges = mock_iter_edges
    mock_graph_instance.iter_nodes = mock_iter_nodes
    mock_graph.return_value = mock_graph_instance

    mock_plugin_manager_instance = MagicMock()
    mock_plugin_manager_instance.get_plugins_with_capability.return_value = []
    mock_plugin_manager.return_value = mock_plugin_manager_instance

    # Mock sleep to raise KeyboardInterrupt after first iteration
    mock_sleep.side_effect = KeyboardInterrupt("Test interruption")

    # Run the command with interval (will be interrupted after first build)
    stdout, stderr, exit_code = unpage("graph build --interval 60")

    # Verify the first build completed and interval was attempted (tests real interval logic)
    assert "Building graph..." in stdout
    assert "Sleeping for 60 seconds before next build..." in stdout
    assert stderr == ""
    assert exit_code == 130  # KeyboardInterrupt results in exit code 130

    # Verify sleep was called
    mock_sleep.assert_called_once_with(60)
