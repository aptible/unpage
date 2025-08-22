"""Tests for the MCP tools call CLI command."""

from unittest.mock import patch, AsyncMock, MagicMock
from mcp.types import TextContent


@patch("unpage.cli.mcp.tools.call.telemetry.send_event")
@patch("unpage.cli.mcp.tools.call.Client")
@patch("unpage.cli.mcp.tools.call.build_mcp_server")
def test_call_tool_success(
    mock_build_server, mock_client_class, mock_send_event, unpage, mock_config_manager
):
    """Test successful tool call.

    Should:
    - Build MCP server and check tool exists
    - Call tool with provided arguments
    - Display tool result content
    - Exit with code 0 (success)
    """
    # Mock external systems
    mock_send_event.return_value = None

    # Mock MCP server with a test tool
    test_tool = MagicMock()
    test_tool.parameters = {"properties": {"query": {"type": "string"}}}

    mock_mcp_server = AsyncMock()
    mock_mcp_server.get_tools.return_value = {"test_tool": test_tool}
    mock_build_server.return_value = mock_mcp_server

    # Mock client and tool call result
    mock_client = AsyncMock()
    mock_client_class.return_value = mock_client
    mock_result = AsyncMock()
    mock_result.content = [TextContent(text="Tool executed successfully", type="text")]
    mock_client.call_tool.return_value = mock_result

    # Run the command
    stdout, stderr, exit_code = unpage("mcp tools call test_tool")

    # Verify success (tests real result processing logic)
    assert stderr == ""
    assert exit_code == 0
    assert "Tool executed successfully" in stdout

    # Verify tool was called
    mock_client.call_tool.assert_called_once_with("test_tool", {})


@patch("unpage.cli.mcp.tools.call.telemetry.send_event")
@patch("unpage.cli.mcp.tools.call.build_mcp_server")
def test_call_tool_not_found(mock_build_server, mock_send_event, unpage, mock_config_manager):
    """Test calling tool that doesn't exist.

    Should:
    - Build MCP server and check available tools
    - Exit with code 1 (error) when tool not found
    """
    # Mock external systems
    mock_send_event.return_value = None

    # Mock MCP server with no matching tool
    other_tool = MagicMock()
    other_tool.parameters = {"properties": {}}

    mock_mcp_server = AsyncMock()
    mock_mcp_server.get_tools.return_value = {"other_tool": other_tool}
    mock_build_server.return_value = mock_mcp_server

    # Run the command with non-existent tool
    stdout, stderr, exit_code = unpage("mcp tools call nonexistent_tool")

    # Verify error handling (tests real error handling logic)
    assert "Tool nonexistent_tool not found" in stdout
    assert stderr == ""
    assert exit_code == 1


@patch("unpage.cli.mcp.tools.call.telemetry.send_event")
@patch("unpage.cli.mcp.tools.call.Client")
@patch("unpage.cli.mcp.tools.call.build_mcp_server")
def test_call_tool_with_arguments(
    mock_build_server, mock_client_class, mock_send_event, unpage, mock_config_manager
):
    """Test calling tool with arguments.

    Should:
    - Parse arguments and convert to tool parameters
    - Handle JSON argument parsing for complex types
    - Call tool with parsed arguments
    - Exit with code 0 (success)
    """
    # Mock external systems
    mock_send_event.return_value = None

    # Mock MCP server with a tool that takes arguments
    search_tool = MagicMock()
    search_tool.parameters = {
        "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer"},
            "filters": {"type": "object"},
        }
    }

    mock_mcp_server = AsyncMock()
    mock_mcp_server.get_tools.return_value = {"search_tool": search_tool}
    mock_build_server.return_value = mock_mcp_server

    # Mock client and tool call result
    mock_client = AsyncMock()
    mock_client_class.return_value = mock_client
    mock_result = AsyncMock()
    mock_result.content = [TextContent(text="Search results: 5 items found", type="text")]
    mock_client.call_tool.return_value = mock_result

    # Run the command with arguments using multiple --arguments flags
    stdout, stderr, exit_code = unpage(
        'mcp tools call search_tool --arguments "test query" --arguments "10" --arguments "{\\"status\\": \\"active\\"}"'
    )

    # Verify success (tests real argument parsing logic)
    assert stderr == ""
    assert exit_code == 0
    assert "Search results: 5 items found" in stdout

    # Verify tool was called with parsed arguments (tests real JSON parsing)
    expected_args = {
        "query": "test query",
        "limit": 10,  # Should be parsed as JSON integer
        "filters": {"status": "active"},  # Should be parsed as JSON object
    }
    mock_client.call_tool.assert_called_once_with("search_tool", expected_args)


@patch("unpage.cli.mcp.tools.call.telemetry.send_event")
@patch("unpage.cli.mcp.tools.call.Client")
@patch("unpage.cli.mcp.tools.call.build_mcp_server")
def test_call_tool_count_results(
    mock_build_server, mock_client_class, mock_send_event, unpage, mock_config_manager
):
    """Test calling tool with count_results flag.

    Should:
    - Call tool and get results
    - Count results instead of displaying content
    - Handle different count levels appropriately
    - Exit with code 0 (success)
    """
    # Mock external systems
    mock_send_event.return_value = None

    # Mock MCP server with a list tool
    list_tool = MagicMock()
    list_tool.parameters = {"properties": {}}

    mock_mcp_server = AsyncMock()
    mock_mcp_server.get_tools.return_value = {"list_tool": list_tool}
    mock_build_server.return_value = mock_mcp_server

    # Mock client and tool call result with a list
    mock_client = AsyncMock()
    mock_client_class.return_value = mock_client
    mock_result = AsyncMock()
    test_list = ["item1", "item2", "item3", "item4", "item5"]
    mock_result.content = [TextContent(text=str(test_list).replace("'", '"'), type="text")]
    mock_client.call_tool.return_value = mock_result

    # Run the command with count_results flag
    stdout, stderr, exit_code = unpage("mcp tools call list_tool --count-results")

    # Verify success and count output
    assert stderr == ""
    assert exit_code == 0
    assert '"count": 5' in stdout  # Should count the 5 items in the list
    assert '"content_length"' in stdout  # Should include content length

    # Verify tool was called
    mock_client.call_tool.assert_called_once_with("list_tool", {})


@patch("unpage.cli.mcp.tools.call.telemetry.send_event")
@patch("unpage.cli.mcp.tools.call.Client")
@patch("unpage.cli.mcp.tools.call.build_mcp_server")
def test_call_tool_no_printable_results(
    mock_build_server, mock_client_class, mock_send_event, unpage, mock_config_manager
):
    """Test calling tool that returns no printable results.

    Should:
    - Handle StopIteration when no TextContent found
    - Display appropriate message for no results
    - Exit with code 0 (success)
    """
    # Mock external systems
    mock_send_event.return_value = None

    # Mock MCP server with a tool
    action_tool = MagicMock()
    action_tool.parameters = {"properties": {}}

    mock_mcp_server = AsyncMock()
    mock_mcp_server.get_tools.return_value = {"action_tool": action_tool}
    mock_build_server.return_value = mock_mcp_server

    # Mock client and tool call result with no TextContent
    mock_client = AsyncMock()
    mock_client_class.return_value = mock_client
    mock_result = AsyncMock()
    mock_result.content = []  # No content, will cause StopIteration
    mock_client.call_tool.return_value = mock_result

    # Run the command
    stdout, stderr, exit_code = unpage("mcp tools call action_tool")

    # Verify success with appropriate message
    assert stderr == ""
    assert exit_code == 0
    assert "action_tool returned no printable results" in stdout

    # Verify tool was called
    mock_client.call_tool.assert_called_once_with("action_tool", {})
