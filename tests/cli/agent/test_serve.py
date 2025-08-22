"""Tests for the agent serve CLI command."""

from unittest.mock import patch


@patch("unpage.cli.agent.serve.telemetry.send_event")
@patch("unpage.cli.agent.serve.listen")
def test_serve_default_settings(mock_listen, mock_send_event, unpage, test_profile):
    """Test serve command with default settings.

    Should:
    - Start server with default host, port, and worker settings
    - Call listen() function with correct parameters
    - Exit with code 0 (success)
    """
    # Mock external systems
    mock_send_event.return_value = None
    mock_listen.return_value = None

    # Run the command with default settings
    stdout, stderr, exit_code = unpage("agent serve")

    # Verify success and exit code
    assert stderr == ""
    assert exit_code == 0

    # Verify listen was called with default parameters
    mock_listen.assert_called_once()
    call_kwargs = mock_listen.call_args.kwargs

    # Check that default values are used (these come from settings)
    assert "host" in call_kwargs
    assert "port" in call_kwargs
    assert "workers" in call_kwargs
    assert "tunnel" in call_kwargs
    assert "ngrok_token" in call_kwargs
    assert "ngrok_domain" in call_kwargs
    assert "reload" in call_kwargs


@patch("unpage.cli.agent.serve.telemetry.send_event")
@patch("unpage.cli.agent.serve.listen")
def test_serve_custom_settings(mock_listen, mock_send_event, unpage, test_profile):
    """Test serve command with custom host, port, and worker settings.

    Should:
    - Start server with provided custom settings
    - Call listen() function with custom parameters
    - Exit with code 0 (success)
    """
    # Mock external systems
    mock_send_event.return_value = None
    mock_listen.return_value = None

    # Run the command with custom settings
    stdout, stderr, exit_code = unpage("agent serve --host 0.0.0.0 --port 9000 --workers 4")

    # Verify success and exit code
    assert stderr == ""
    assert exit_code == 0

    # Verify listen was called with custom parameters
    mock_listen.assert_called_once()
    call_kwargs = mock_listen.call_args.kwargs

    # Check that custom values are used
    assert call_kwargs["host"] == "0.0.0.0"
    assert call_kwargs["port"] == 9000
    assert call_kwargs["workers"] == 4


@patch("unpage.cli.agent.serve.telemetry.send_event")
@patch("unpage.cli.agent.serve.listen")
def test_serve_with_tunnel(mock_listen, mock_send_event, unpage, test_profile):
    """Test serve command with tunnel enabled.

    Should:
    - Start server with tunnel configuration
    - Use provided ngrok token and domain if specified
    - Exit with code 0 (success)
    """
    # Mock external systems
    mock_send_event.return_value = None
    mock_listen.return_value = None

    # Run the command with tunnel enabled
    stdout, stderr, exit_code = unpage("agent serve --tunnel --ngrok-domain test.ngrok.io")

    # Verify success and exit code
    assert stderr == ""
    assert exit_code == 0

    # Verify listen was called with tunnel parameters
    mock_listen.assert_called_once()
    call_kwargs = mock_listen.call_args.kwargs

    # Check that tunnel settings are used
    assert call_kwargs["tunnel"] is True
    assert call_kwargs["ngrok_domain"] == "test.ngrok.io"
