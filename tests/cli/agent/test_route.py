"""Tests for the agent route CLI command."""

from unittest.mock import patch, AsyncMock


@patch("unpage.cli.agent.route.telemetry.send_event")
@patch("unpage.cli.agent.route.AnalysisAgent")
@patch("sys.stdin")
def test_route_with_payload_argument(
    mock_stdin, mock_analysis_agent, mock_send_event, unpage, test_profile
):
    """Test route command with payload passed as argument.

    Should:
    - Accept payload argument
    - Call AnalysisAgent with route_only=True
    - Display routing result
    - Exit with code 0 (success)
    """
    # Mock external systems
    mock_send_event.return_value = None
    mock_stdin.isatty.return_value = True  # No piped input
    mock_agent_instance = AsyncMock()
    mock_agent_instance.acall.return_value = "Routing to: incident-response-agent"
    mock_analysis_agent.return_value = mock_agent_instance

    # Run the command with payload argument
    stdout, stderr, exit_code = unpage('agent route "test payload data"')

    # Verify success and routing result
    assert "Routing to: incident-response-agent" in stdout
    assert stderr == ""
    assert exit_code == 0

    # Verify AnalysisAgent was called correctly
    mock_analysis_agent.assert_called_once()
    mock_agent_instance.acall.assert_called_once_with(payload="test payload data", route_only=True)


@patch("unpage.cli.agent.route.telemetry.send_event")
@patch("unpage.cli.agent.route.AnalysisAgent")
@patch("sys.stdin")
def test_route_with_stdin(mock_stdin, mock_analysis_agent, mock_send_event, unpage, test_profile):
    """Test route command with payload from stdin.

    Should:
    - Read payload from stdin when available
    - Call AnalysisAgent with route_only=True
    - Display routing result
    - Exit with code 0 (success)
    """
    # Mock external systems
    mock_send_event.return_value = None
    mock_stdin.isatty.return_value = False  # Simulate piped input
    mock_stdin.read.return_value = "piped payload data\n"
    mock_agent_instance = AsyncMock()
    mock_agent_instance.acall.return_value = "Routing to: log-analysis-agent"
    mock_analysis_agent.return_value = mock_agent_instance

    # Run the command without payload argument (stdin mode)
    stdout, stderr, exit_code = unpage("agent route")

    # Verify success and routing result
    assert "Routing to: log-analysis-agent" in stdout
    assert stderr == ""
    assert exit_code == 0

    # Verify AnalysisAgent was called with stdin data
    mock_agent_instance.acall.assert_called_once_with(payload="piped payload data", route_only=True)


@patch("unpage.cli.agent.route.telemetry.send_event")
@patch("sys.stdin")
def test_route_payload_and_stdin_conflict(mock_stdin, mock_send_event, unpage, test_profile):
    """Test route command with both payload argument and stdin.

    Should:
    - Detect conflict between payload argument and stdin
    - Exit with code 1 (error) when both provided
    """
    # Mock external systems
    mock_send_event.return_value = None
    mock_stdin.isatty.return_value = False  # Simulate piped input

    # Run the command with both payload argument and stdin
    stdout, stderr, exit_code = unpage('agent route "payload arg"')

    # Verify error message and exit code
    assert "Cannot pass a payload argument when piping data to stdin" in stdout
    assert stderr == ""
    assert exit_code == 1


@patch("unpage.cli.agent.route.telemetry.send_event")
@patch("sys.stdin")
def test_route_no_payload(mock_stdin, mock_send_event, unpage, test_profile):
    """Test route command with no payload provided.

    Should:
    - Detect missing payload data
    - Exit with code 1 (error) when no payload available
    """
    # Mock external systems
    mock_send_event.return_value = None
    mock_stdin.isatty.return_value = True  # No piped input

    # Run the command without payload
    stdout, stderr, exit_code = unpage("agent route")

    # Verify error message and exit code
    assert "No payload provided" in stdout
    assert "Pass an alert payload as an argument or pipe the payload data to stdin" in stdout
    assert stderr == ""
    assert exit_code == 1


@patch("unpage.cli.agent.route.telemetry.send_event")
@patch("unpage.cli.agent.route.AnalysisAgent")
@patch("sys.stdin")
def test_route_analysis_failure(
    mock_stdin, mock_analysis_agent, mock_send_event, unpage, test_profile
):
    """Test route command when analysis fails.

    Should:
    - Handle exception from AnalysisAgent
    - Exit with code 1 (error) when analysis fails
    """
    # Mock external systems
    mock_send_event.return_value = None
    mock_stdin.isatty.return_value = True  # No piped input
    mock_agent_instance = AsyncMock()
    mock_agent_instance.acall.side_effect = Exception("Analysis failed: Invalid payload format")
    mock_analysis_agent.return_value = mock_agent_instance

    # Run the command with payload that will cause analysis to fail
    stdout, stderr, exit_code = unpage('agent route "invalid payload"')

    # Verify error message and exit code
    assert "Analysis failed:" in stdout
    assert "Invalid payload format" in stdout
    assert stderr == ""
    assert exit_code == 1

    # Verify AnalysisAgent was called
    mock_agent_instance.acall.assert_called_once_with(payload="invalid payload", route_only=True)
