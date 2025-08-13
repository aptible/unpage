"""Tests for the MCP tools list CLI command."""

from unittest.mock import patch, AsyncMock, MagicMock


@patch("unpage.cli.mcp.tools.list.telemetry.send_event")
@patch("unpage.cli.mcp.tools.list.build_mcp_server")
def test_list_tools_success(mock_build_server, mock_send_event, unpage, mock_config_manager):
    """Test successful listing of MCP tools.

    Should:
    - Build MCP server with current context
    - Call get_tools() to retrieve available tools
    - Display tools with their parameter signatures
    - Exit with code 0 (success)
    """
    # Mock external systems
    mock_send_event.return_value = None

    # Mock MCP server with sample tools
    # Create tool objects with parameters attribute
    search_logs_tool = MagicMock()
    search_logs_tool.parameters = {
        "properties": {
            "query": {"type": "string"},
            "start_time": {"type": "string"},
            "limit": {"type": "integer"},
        }
    }

    get_metrics_tool = MagicMock()
    get_metrics_tool.parameters = {
        "properties": {
            "service": {"type": "string"},
            "metric_type": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        }
    }

    mock_mcp_server = AsyncMock()
    mock_mcp_server.get_tools.return_value = {
        "search_logs": search_logs_tool,
        "get_metrics": get_metrics_tool,
    }
    mock_build_server.return_value = mock_mcp_server

    # Run the command
    stdout, stderr, exit_code = unpage("mcp tools list")

    # Verify success
    assert stderr == ""
    assert exit_code == 0

    # Verify tools are displayed with their signatures (tests real formatting logic)
    assert "search_logs <query:string> <start_time:string> <limit:integer>" in stdout
    assert "get_metrics <service:string> <metric_type:string|null>" in stdout

    # Verify MCP server was built and tools retrieved
    mock_build_server.assert_called_once()
    mock_mcp_server.get_tools.assert_called_once()


@patch("unpage.cli.mcp.tools.list.telemetry.send_event")
@patch("unpage.cli.mcp.tools.list.build_mcp_server")
def test_list_tools_empty(mock_build_server, mock_send_event, unpage, mock_config_manager):
    """Test listing tools when no tools are available.

    Should:
    - Build MCP server with context
    - Display error message when no tools available
    - Exit with code 1 (error)
    """
    # Mock external systems
    mock_send_event.return_value = None

    # Mock MCP server with no tools
    mock_mcp_server = AsyncMock()
    mock_mcp_server.get_tools.return_value = {}
    mock_build_server.return_value = mock_mcp_server

    # Run the command
    stdout, stderr, exit_code = unpage("mcp tools list")

    # Verify error message and exit code (tests real error handling logic)
    assert "No MCP tools available from enabled plugins" in stdout
    assert "Enable plugins with 'unpage configure' to access more tools" in stdout
    assert stderr == ""
    assert exit_code == 1

    # Verify MCP server operations
    mock_build_server.assert_called_once()
    mock_mcp_server.get_tools.assert_called_once()
