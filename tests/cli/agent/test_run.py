"""Tests for the agent run CLI command."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


@patch("unpage.cli.agent.run.telemetry.send_event")
@patch("unpage.cli.agent.run.AnalysisAgent")
@patch("sys.stdin")
def test_run_with_payload_argument(
    mock_stdin, mock_analysis_agent, mock_send_event, unpage, test_profile
):
    """Test run command with payload passed as argument.

    Should:
    - Accept agent_name and payload arguments
    - Load the specified agent
    - Call AnalysisAgent with payload and agent
    - Display analysis result
    - Exit with code 0 (success)
    """
    # Create test agent file
    agents_dir = test_profile / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    test_agent_file = agents_dir / "test-agent.yaml"
    test_agent_file.write_text("""description: Test agent for integration testing
prompt: Test agent prompt
tools:
  - "*"
""")

    # Mock external systems
    mock_send_event.return_value = None
    mock_stdin.isatty.return_value = True  # No piped input
    mock_agent_instance = AsyncMock()
    mock_agent_instance.acall.return_value = "Analysis complete: No issues detected"
    mock_analysis_agent.return_value = mock_agent_instance

    # Run the command with agent name and payload argument
    stdout, stderr, exit_code = unpage('agent run test-agent "test payload data"')

    # Verify success and analysis result
    assert "Analysis complete: No issues detected" in stdout
    assert stderr == ""
    assert exit_code == 0

    # Verify AnalysisAgent was called correctly (agent loading is real)
    mock_analysis_agent.assert_called_once()
    mock_agent_instance.acall.assert_called_once()
    call_args = mock_agent_instance.acall.call_args
    assert call_args.kwargs["payload"] == "test payload data"
    assert call_args.kwargs["agent"] is not None  # Agent was loaded successfully


@patch("sys.stdin")
@patch("unpage.cli.agent.run.load_agent")
@patch("unpage.cli.agent.run.AnalysisAgent")
@patch("unpage.cli.agent.run.PluginManager")
@patch("unpage.cli.agent.run.telemetry.send_event")
def test_run_with_stdin(
    mock_send_event, mock_plugin_manager, mock_analysis_agent, mock_load_agent, mock_stdin, unpage
):
    """Test run command with payload from stdin.

    Should:
    - Read payload from stdin when available
    - Load the specified agent
    - Call AnalysisAgent with stdin data and agent
    - Display analysis result
    - Exit with code 0 (success)
    """
    # Setup mocks
    mock_send_event.return_value = None
    mock_stdin.isatty.return_value = False  # Simulate piped input
    mock_stdin.read.return_value = "piped payload data\n"
    mock_agent = {"name": "log-agent", "prompt": "Log analysis agent"}
    mock_load_agent.return_value = mock_agent
    mock_plugin_manager.return_value = None
    mock_agent_instance = AsyncMock()
    mock_agent_instance.acall.return_value = "Log analysis: Critical error detected in service"
    mock_analysis_agent.return_value = mock_agent_instance

    # Run the command without payload argument (stdin mode)
    stdout, stderr, exit_code = unpage("agent run log-agent")

    # Verify success and analysis result
    assert "Log analysis: Critical error detected in service" in stdout
    assert stderr == ""
    assert exit_code == 0

    # Verify agent was loaded and AnalysisAgent was called with stdin data
    mock_load_agent.assert_called_once_with("log-agent")
    mock_agent_instance.acall.assert_called_once_with(
        payload="piped payload data", agent=mock_agent
    )


@patch("sys.stdin")
@patch("unpage.cli.agent.run.load_agent")
@patch("unpage.cli.agent.run.AnalysisAgent")
@patch("unpage.cli.agent.run.PluginManager")
@patch("unpage.cli.agent.run.manager")
@patch("unpage.cli.agent.run.telemetry.send_event")
def test_run_with_pagerduty_incident(
    mock_send_event,
    mock_manager,
    mock_plugin_manager,
    mock_analysis_agent,
    mock_load_agent,
    mock_stdin,
    unpage,
):
    """Test run command with PagerDuty incident.

    Should:
    - Fetch incident data from PagerDuty plugin
    - Load the specified agent
    - Call AnalysisAgent with incident data and agent
    - Display analysis result
    - Exit with code 0 (success)
    """
    # Setup mocks
    mock_send_event.return_value = None
    mock_manager.get_active_profile.return_value = "default"  # Must be string for telemetry
    mock_manager.get_active_profile_config.return_value = {"plugins": {}}
    mock_stdin.isatty.return_value = True  # No piped input
    mock_agent = {"name": "incident-agent", "prompt": "Incident analysis agent"}
    mock_load_agent.return_value = mock_agent

    # Mock PagerDuty plugin and incident
    mock_incident = MagicMock()
    mock_incident.model_dump_json.return_value = '{"id": "P123", "title": "Test incident"}'

    # Create a regular mock plugin with async method
    mock_pd_plugin = MagicMock()

    # Set up the async method as AsyncMock
    mock_pd_plugin.get_incident_by_id = AsyncMock(return_value=mock_incident)

    mock_plugin_manager_instance = MagicMock()
    mock_plugin_manager_instance.get_plugin.return_value = mock_pd_plugin
    mock_plugin_manager.return_value = mock_plugin_manager_instance

    mock_agent_instance = AsyncMock()
    mock_agent_instance.acall.return_value = "Incident analysis: Service degradation detected"
    mock_analysis_agent.return_value = mock_agent_instance

    # Run the command with PagerDuty incident
    stdout, stderr, exit_code = unpage("agent run incident-agent --pagerduty-incident P123")

    # Verify success and analysis result
    assert "Incident analysis: Service degradation detected" in stdout
    assert stderr == ""
    assert exit_code == 0

    # Verify PagerDuty incident was fetched and used
    mock_plugin_manager_instance.get_plugin.assert_called_once_with("pagerduty")
    mock_pd_plugin.get_incident_by_id.assert_called_once_with("P123")
    mock_agent_instance.acall.assert_called_once_with(
        payload='{"id": "P123", "title": "Test incident"}', agent=mock_agent
    )


@patch("sys.stdin")
@patch("unpage.cli.agent.run.telemetry.send_event")
def test_run_payload_and_stdin_conflict(mock_send_event, mock_stdin, unpage):
    """Test run command with both payload argument and stdin.

    Should:
    - Detect conflict between payload argument and stdin
    - Exit with code 1 (error) when both provided
    """
    # Setup mocks
    mock_send_event.return_value = None
    mock_stdin.isatty.return_value = False  # Simulate piped input

    # Run the command with both payload argument and stdin
    stdout, stderr, exit_code = unpage('agent run test-agent "payload arg"')

    # Verify error message and exit code
    assert "Cannot pass a payload argument when piping data to stdin" in stdout
    assert stderr == ""
    assert exit_code == 1


@patch("sys.stdin")
@patch("unpage.cli.agent.run.telemetry.send_event")
def test_run_pagerduty_and_payload_conflict(mock_send_event, mock_stdin, unpage):
    """Test run command with both PagerDuty incident and payload.

    Should:
    - Detect conflict between --pagerduty-incident and payload/stdin
    - Exit with code 1 (error) when both provided
    """
    # Setup mocks
    mock_send_event.return_value = None
    mock_stdin.isatty.return_value = True  # No piped input

    # Run the command with both PagerDuty incident and payload
    stdout, stderr, exit_code = unpage('agent run test-agent "payload" --pagerduty-incident P123')

    # Verify error message and exit code
    assert stderr == ""
    assert (
        "Cannot pass --pagerduty-incident, --rootly-incident, or --use-test-payload with" in stdout
    )
    assert exit_code == 1


@patch("sys.stdin")
@patch("unpage.cli.agent.run.telemetry.send_event")
def test_run_no_payload(mock_send_event, mock_stdin, unpage):
    """Test run command with no payload provided.

    Should:
    - Detect missing payload data
    - Exit with code 1 (error) when no payload available
    """
    # Setup mocks
    mock_send_event.return_value = None
    mock_stdin.isatty.return_value = True  # No piped input

    # Run the command without payload
    stdout, stderr, exit_code = unpage("agent run test-agent")

    # Verify error message and exit code
    assert "No payload provided" in stdout
    assert "Pass an alert payload as an argument or pipe the payload data to stdin" in stdout
    assert stderr == ""
    assert exit_code == 1


@patch("sys.stdin")
@patch("unpage.cli.agent.run.load_agent")
@patch("unpage.cli.agent.run.PluginManager")
@patch("unpage.cli.agent.run.telemetry.send_event")
def test_run_agent_not_found(
    mock_send_event, mock_plugin_manager, mock_load_agent, mock_stdin, unpage
):
    """Test run command when agent file is not found.

    Should:
    - Handle FileNotFoundError from load_agent
    - Exit with code 1 (error) when agent doesn't exist
    """
    # Setup mocks
    mock_send_event.return_value = None
    mock_stdin.isatty.return_value = True  # No piped input
    mock_plugin_manager.return_value = None
    mock_load_agent.side_effect = FileNotFoundError("/path/to/nonexistent-agent.md")
    mock_load_agent.side_effect.filename = "/path/to/nonexistent-agent.md"

    # Run the command with non-existent agent
    stdout, stderr, exit_code = unpage('agent run nonexistent-agent "test payload"')

    # Verify error message and exit code
    assert "Agent 'nonexistent-agent' not found at '/path/to/nonexistent-agent.md'" in stdout
    assert "Use 'unpage agent create 'nonexistent-agent'' to create a new agent" in stdout
    assert stderr == ""
    assert exit_code == 1


@patch("sys.stdin")
@patch("unpage.cli.agent.run.load_agent")
@patch("unpage.cli.agent.run.AnalysisAgent")
@patch("unpage.cli.agent.run.PluginManager")
@patch("unpage.cli.agent.run.telemetry.send_event")
def test_run_analysis_failure(
    mock_send_event, mock_plugin_manager, mock_analysis_agent, mock_load_agent, mock_stdin, unpage
):
    """Test run command when analysis fails.

    Should:
    - Handle exception from AnalysisAgent
    - Exit with code 1 (error) when analysis fails
    """
    # Setup mocks
    mock_send_event.return_value = None
    mock_stdin.isatty.return_value = True  # No piped input
    mock_agent = {"name": "test-agent", "prompt": "Test agent prompt"}
    mock_load_agent.return_value = mock_agent
    mock_plugin_manager.return_value = None
    mock_agent_instance = AsyncMock()
    mock_agent_instance.acall.side_effect = Exception("Analysis failed: Invalid payload format")
    mock_analysis_agent.return_value = mock_agent_instance

    # Run the command with payload that will cause analysis to fail
    stdout, stderr, exit_code = unpage('agent run test-agent "invalid payload"')

    # Verify error message and exit code
    assert "Analysis failed:" in stdout
    assert "Invalid payload format" in stdout
    assert stderr == ""
    assert exit_code == 1

    # Verify AnalysisAgent was called
    mock_agent_instance.acall.assert_called_once_with(payload="invalid payload", agent=mock_agent)
