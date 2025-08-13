"""Tests for the version CLI command."""

import json
from unittest.mock import patch

from unpage import __version__


@patch("unpage.cli.version.telemetry.send_event")
def test_version_default_output_cli(mock_send_event, unpage):
    """Test version command with default text output via CLI.

    Should:
    - Display version information in human-readable format
    - Include actual unpage version
    - Exit with code 0
    """
    # Run the command as a user would
    stdout, stderr, exit_code = unpage("version")

    # Verify output and exit code
    assert f"unpage {__version__}" in stdout
    assert stderr == ""
    assert exit_code == 0


@patch("unpage.cli.version.telemetry.send_event")
def test_version_json_output_cli(mock_send_event, unpage):
    """Test version command with JSON output flag via CLI.

    Should:
    - Display version information as valid JSON
    - Include actual unpage version in JSON format
    - Exit with code 0
    """
    # Run the command as a user would
    stdout, stderr, exit_code = unpage("version --json")

    # Parse and verify JSON output
    data = json.loads(stdout.strip())
    assert data["unpage"] == __version__
    assert stderr == ""
    assert exit_code == 0
