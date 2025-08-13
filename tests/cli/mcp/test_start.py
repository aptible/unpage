"""Tests for the MCP start CLI command."""

from unittest.mock import patch


@patch("unpage.cli.mcp.start.telemetry.send_event")
@patch("unpage.cli.mcp.start.mcp.start")
def test_start_mcp_server_default(mock_mcp_start, mock_send_event, unpage, mock_config_manager):
    """Test starting MCP server with default settings.

    Should:
    - Start MCP server with default transport settings
    - Call mcp.start() with correct parameters
    - Exit with code 0 (success)
    """
    # Mock external systems
    mock_send_event.return_value = None
    mock_mcp_start.return_value = None

    # Run the command
    stdout, stderr, exit_code = unpage("mcp start")

    # Verify success
    assert stderr == ""
    assert exit_code == 0

    # Verify mcp.start was called with default parameters
    mock_mcp_start.assert_called_once_with(
        disable_stdio=False,
        disable_http=False,
        http_host="127.0.0.1",  # Default from fastmcp_settings
        http_port=8000,  # Default from fastmcp_settings (corrected)
    )


@patch("unpage.cli.mcp.start.telemetry.send_event")
@patch("unpage.cli.mcp.start.mcp.start")
def test_start_mcp_server_custom_settings(
    mock_mcp_start, mock_send_event, unpage, mock_config_manager
):
    """Test starting MCP server with custom settings.

    Should:
    - Accept custom host, port, and transport settings
    - Call mcp.start() with provided parameters
    - Exit with code 0 (success)
    """
    # Mock external systems
    mock_send_event.return_value = None
    mock_mcp_start.return_value = None

    # Run the command with custom settings
    stdout, stderr, exit_code = unpage("mcp start --http-host 0.0.0.0 --http-port 8080")

    # Verify success
    assert stderr == ""
    assert exit_code == 0

    # Verify mcp.start was called with custom parameters
    mock_mcp_start.assert_called_once_with(
        disable_stdio=False,
        disable_http=False,
        http_host="0.0.0.0",
        http_port=8080,
    )


@patch("unpage.cli.mcp.start.telemetry.send_event")
@patch("unpage.cli.mcp.start.mcp.start")
def test_start_mcp_server_disable_transports(
    mock_mcp_start, mock_send_event, unpage, mock_config_manager
):
    """Test starting MCP server with disabled transports.

    Should:
    - Accept flags to disable stdio and HTTP transports
    - Call mcp.start() with disabled transports
    - Exit with code 0 (success)
    """
    # Mock external systems
    mock_send_event.return_value = None
    mock_mcp_start.return_value = None

    # Run the command with disabled transports
    stdout, stderr, exit_code = unpage("mcp start --disable-stdio --disable-http")

    # Verify success
    assert stderr == ""
    assert exit_code == 0

    # Verify mcp.start was called with disabled transports
    mock_mcp_start.assert_called_once_with(
        disable_stdio=True,
        disable_http=True,
        http_host="127.0.0.1",
        http_port=8000,  # Corrected default port
    )


@patch("unpage.cli.mcp.start.warnings.warn")
@patch("unpage.cli.mcp.start.sys.argv", ["unpage", "mcp", "start", "--disable-sse"])
@patch("unpage.cli.mcp.start.telemetry.send_event")
@patch("unpage.cli.mcp.start.mcp.start")
def test_start_mcp_server_deprecated_sse_flag(
    mock_mcp_start, mock_send_event, mock_warn, unpage, mock_config_manager
):
    """Test starting MCP server with deprecated --disable-sse flag.

    Should:
    - Handle deprecated --disable-sse flag
    - Map it to --disable-http flag
    - Show deprecation warning
    - Exit with code 0 (success)
    """
    # Mock external systems
    mock_send_event.return_value = None
    mock_mcp_start.return_value = None
    mock_warn.return_value = None

    # Run the command with deprecated flag
    stdout, stderr, exit_code = unpage("mcp start --disable-sse")

    # Verify success
    assert stderr == ""
    assert exit_code == 0

    # Verify deprecation warning was shown
    mock_warn.assert_called_once_with(
        "The `--disable-sse` argument is deprecated. Use `--disable-http` instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    # Verify mcp.start was called with HTTP disabled (mapped from SSE)
    mock_mcp_start.assert_called_once_with(
        disable_stdio=False,
        disable_http=True,  # Should be True due to --disable-sse mapping
        http_host="127.0.0.1",
        http_port=8000,  # Corrected default port
    )
