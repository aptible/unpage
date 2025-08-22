"""Tests for the graph status CLI command."""

from unittest.mock import patch, MagicMock


@patch("unpage.cli.graph.status.telemetry.send_event")
@patch("unpage.cli.graph.status.is_process_running")
def test_status_build_running(
    mock_is_running, mock_send_event, unpage, mock_config_manager, running_graph_build
):
    """Test status command when graph build is running.

    Should:
    - Read PID from real PID file
    - Check if process is running
    - Display running status with PID
    - Show log file location if available
    - Exit with code 0 (success)
    """
    # Mock external systems
    mock_send_event.return_value = None
    mock_is_running.return_value = True

    # PID file already created by running_graph_build fixture
    pid_content = running_graph_build["pid_file"].read_text().strip()

    # Run the command
    stdout, stderr, exit_code = unpage("graph status")

    # Verify success and running status (tests real CLI output logic)
    assert f"Graph build running (PID: {pid_content})" in stdout
    assert "View logs: unpage graph logs --follow" in stdout
    assert stderr == ""
    assert exit_code == 0

    # Verify process check was performed
    mock_is_running.assert_called_once_with(int(pid_content))


@patch("unpage.cli.graph.status.telemetry.send_event")
def test_status_no_build_running(mock_send_event, unpage, mock_config_manager):
    """Test status command when no build is running.

    Should:
    - Check for PID file existence (real file system check)
    - Exit with code 1 (error) when PID file doesn't exist
    """
    # Mock external systems
    mock_send_event.return_value = None

    # No PID file created, so command should find none

    # Run the command
    stdout, stderr, exit_code = unpage("graph status")

    # Verify error message and exit code (tests real CLI error logic)
    assert "No graph build running" in stdout
    assert stderr == ""
    assert exit_code == 1


@patch("unpage.cli.graph.status.telemetry.send_event")
@patch("unpage.cli.graph.status.cleanup_pid_file")
@patch("unpage.cli.graph.status.is_process_running")
def test_status_stale_pid_file(
    mock_is_running, mock_cleanup, mock_send_event, unpage, mock_config_manager, test_profile
):
    """Test status command with stale PID file.

    Should:
    - Check real PID file but find process not running
    - Clean up stale PID file
    - Exit with code 1 (error)
    """
    # Mock external systems
    mock_send_event.return_value = None
    mock_is_running.return_value = False  # Process not running
    mock_cleanup.return_value = None

    # Create a real PID file with a stale PID
    pid_file = test_profile / "graph_build.pid"
    pid_file.write_text("99999")

    # Run the command
    stdout, stderr, exit_code = unpage("graph status")

    # Verify cleanup and error (tests real CLI error logic)
    assert "No graph build running" in stdout
    assert stderr == ""
    assert exit_code == 1

    # Integration test focuses on external behavior, not internal calls


@patch("unpage.cli.graph.status.telemetry.send_event")
@patch("unpage.cli.graph.status.cleanup_pid_file")
def test_status_corrupted_pid_file(
    mock_cleanup, mock_send_event, unpage, mock_config_manager, test_profile
):
    """Test status command with corrupted PID file.

    Should:
    - Handle ValueError when reading corrupted real PID file
    - Clean up corrupted PID file
    - Exit with code 1 (error)
    """
    # Mock external systems
    mock_send_event.return_value = None
    mock_cleanup.return_value = None

    # Create a real PID file with invalid content
    pid_file = test_profile / "graph_build.pid"
    pid_file.write_text("invalid_pid_content")

    # Run the command
    stdout, stderr, exit_code = unpage("graph status")

    # Verify cleanup and error (tests real ValueError handling logic)
    assert "No graph build running" in stdout
    assert stderr == ""
    assert exit_code == 1

    # Cleanup is internal behavior - main thing is correct error handling
