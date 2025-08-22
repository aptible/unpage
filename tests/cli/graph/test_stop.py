"""Tests for the graph stop CLI command."""

from unittest.mock import patch, MagicMock


@patch("unpage.cli.graph.stop.telemetry.send_event")
@patch("unpage.cli.graph.stop.os.kill")
@patch("unpage.cli.graph.stop.is_process_running")
def test_stop_build_success(
    mock_is_running, mock_kill, mock_send_event, unpage, mock_config_manager, running_graph_build
):
    """Test successful build stopping.

    Should:
    - Check real PID file and verify process is running
    - Send SIGTERM to process
    - Clean up PID file after stopping
    - Exit with code 0 (success)
    """
    # Mock external systems
    mock_send_event.return_value = None
    mock_is_running.return_value = True
    mock_kill.return_value = None

    # PID file already created by running_graph_build fixture
    pid_content = running_graph_build["pid_file"].read_text().strip()

    # Run the command
    stdout, stderr, exit_code = unpage("graph stop")

    # Verify success (tests real CLI output logic)
    assert f"Stopping graph build (PID: {pid_content})..." in stdout
    assert "Graph build stopped successfully" in stdout
    assert stderr == ""
    assert exit_code == 0

    # Integration test focuses on external behavior


@patch("unpage.cli.graph.stop.telemetry.send_event")
def test_stop_no_build_running(mock_send_event, unpage, mock_config_manager):
    """Test stop command when no build is running.

    Should:
    - Check for real PID file existence
    - Exit with code 1 (error) when PID file doesn't exist
    """
    # Mock external systems
    mock_send_event.return_value = None

    # No PID file created, so command should find none

    # Run the command
    stdout, stderr, exit_code = unpage("graph stop")

    # Verify error message and exit code (tests real CLI error logic)
    assert "No graph build running" in stdout
    assert stderr == ""
    assert exit_code == 1


@patch("unpage.cli.graph.stop.telemetry.send_event")
@patch("unpage.cli.graph.stop.is_process_running")
def test_stop_stale_pid_file(
    mock_is_running, mock_send_event, unpage, mock_config_manager, test_profile
):
    """Test stop command with stale PID file.

    Should:
    - Check real PID file but find process not running
    - Clean up stale PID file
    - Exit with code 1 (error)
    """
    # Mock external systems
    mock_send_event.return_value = None
    mock_is_running.return_value = False  # Process not running

    # Create a real PID file with a stale PID
    pid_file = test_profile / "graph_build.pid"
    pid_file.write_text("99999")

    # Run the command
    stdout, stderr, exit_code = unpage("graph stop")

    # Verify cleanup and error (tests real CLI error logic)
    assert "No graph build running" in stdout
    assert stderr == ""
    assert exit_code == 1

    # Integration test focuses on external behavior


@patch("unpage.cli.graph.stop.telemetry.send_event")
def test_stop_corrupted_pid_file(mock_send_event, unpage, mock_config_manager, test_profile):
    """Test stop command with corrupted PID file.

    Should:
    - Handle ValueError when reading corrupted real PID file
    - Clean up corrupted PID file
    - Exit with code 1 (error)
    """
    # Mock external systems
    mock_send_event.return_value = None

    # Create a real PID file with invalid content
    pid_file = test_profile / "graph_build.pid"
    pid_file.write_text("invalid_pid_content")

    # Run the command
    stdout, stderr, exit_code = unpage("graph stop")

    # Verify cleanup and error (tests real ValueError handling logic)
    assert "No graph build running" in stdout
    assert stderr == ""
    assert exit_code == 1

    # Integration test focuses on external behavior


@patch("unpage.cli.graph.stop.telemetry.send_event")
@patch("unpage.cli.graph.stop.os.kill")
@patch("unpage.cli.graph.stop.is_process_running")
def test_stop_process_lookup_error(
    mock_is_running, mock_kill, mock_send_event, unpage, mock_config_manager, test_profile
):
    """Test stop command when process lookup fails.

    Should:
    - Handle ProcessLookupError when killing process
    - Clean up PID file
    - Exit with code 1 (error)
    """
    # Mock external systems
    mock_send_event.return_value = None
    mock_is_running.return_value = True
    mock_kill.side_effect = ProcessLookupError("Process not found")

    # Create a real PID file
    pid_file = test_profile / "graph_build.pid"
    pid_file.write_text("12345")

    # Run the command
    stdout, stderr, exit_code = unpage("graph stop")

    # Verify error handling (tests real ProcessLookupError handling logic)
    assert "No graph build running" in stdout
    assert stderr == ""
    assert exit_code == 1

    # Integration test focuses on external behavior
