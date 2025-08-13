"""Tests for the graph logs CLI command."""

from unittest.mock import patch, MagicMock, AsyncMock


@patch("unpage.cli.graph.logs.telemetry.send_event")
@patch("unpage.cli.graph.logs.asyncio.create_subprocess_shell")
@patch("unpage.cli.graph.logs.shutil.which")
def test_logs_tail_command_available(
    mock_which, mock_subprocess, mock_send_event, unpage, mock_config_manager, running_graph_build
):
    """Test logs command when tail command is available.

    Should:
    - Check for tail command using shutil.which()
    - Display log content when real log file exists
    - Exit with code 0 (success)
    """
    # Mock external systems
    mock_send_event.return_value = None
    mock_which.return_value = "/usr/bin/tail"

    mock_process = AsyncMock()
    mock_process.wait.return_value = 0
    mock_subprocess.return_value = mock_process

    # Log file already created by running_graph_build fixture
    log_file_path = str(running_graph_build["log_file"])

    # Run the command
    stdout, stderr, exit_code = unpage("graph logs")

    # Verify success (tests real CLI output logic)
    assert "Recent logs:" in stdout
    assert f"Log file: {log_file_path}" in stdout
    assert stderr == ""
    assert exit_code == 0

    # Integration test focuses on external behavior


@patch("unpage.cli.graph.logs.telemetry.send_event")
@patch("unpage.cli.graph.logs.shutil.which")
def test_logs_tail_command_missing(mock_which, mock_send_event, unpage, mock_config_manager):
    """Test logs command when tail command is not available.

    Should:
    - Check for tail command using shutil.which()
    - Exit with code 1 (error) when tail command not found
    """
    # Mock external systems
    mock_send_event.return_value = None
    mock_which.return_value = None  # tail command not found

    # Run the command
    stdout, stderr, exit_code = unpage("graph logs")

    # Verify error message and exit code (tests real CLI error logic)
    assert "'tail' command not found. Please install it." in stdout
    assert stderr == ""
    assert exit_code == 1


@patch("unpage.cli.graph.logs.telemetry.send_event")
@patch("unpage.cli.graph.logs.shutil.which")
def test_logs_file_missing(mock_which, mock_send_event, unpage, mock_config_manager, test_profile):
    """Test logs command when log file doesn't exist.

    Should:
    - Check if real log file exists
    - Exit with code 1 (error) when log file not found
    """
    # Mock external systems
    mock_send_event.return_value = None
    mock_which.return_value = "/usr/bin/tail"

    # No log file created, so command should find none
    expected_log_path = test_profile / "graph_build.log"

    # Run the command
    stdout, stderr, exit_code = unpage("graph logs")

    # Verify error message and exit code (tests real file existence checking)
    assert "No log file found" in stdout
    assert f"Expected location: {expected_log_path}" in stdout
    assert stderr == ""
    assert exit_code == 1


@patch("unpage.cli.graph.logs.telemetry.send_event")
@patch("unpage.cli.graph.logs.asyncio.create_subprocess_shell")
@patch("unpage.cli.graph.logs.shutil.which")
def test_logs_follow_mode(
    mock_which, mock_subprocess, mock_send_event, unpage, mock_config_manager, running_graph_build
):
    """Test logs command with follow flag.

    Should:
    - Run tail with -f flag when follow=True
    - Handle KeyboardInterrupt gracefully
    - Exit with code 0 (success)
    """
    # Mock external systems
    mock_send_event.return_value = None
    mock_which.return_value = "/usr/bin/tail"

    # Mock subprocess to raise KeyboardInterrupt
    mock_process = AsyncMock()
    mock_process.wait.side_effect = KeyboardInterrupt("User interruption")
    mock_subprocess.return_value = mock_process

    # Log file already created by running_graph_build fixture
    log_file_path = str(running_graph_build["log_file"])

    # Run the command with follow flag
    stdout, stderr, exit_code = unpage("graph logs --follow")

    # Verify follow mode messages and graceful handling (tests real KeyboardInterrupt logic)
    assert "Following logs (Ctrl+C to stop)" in stdout
    assert f"Log file: {log_file_path}" in stdout
    assert "Stopped following logs" in stdout
    assert stderr == ""
    assert exit_code == 0

    # Integration test focuses on external behavior
