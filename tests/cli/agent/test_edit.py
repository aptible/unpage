"""Tests for the agent edit CLI command."""

from unittest.mock import patch


@patch("unpage.cli.agent.edit.edit_file")
def test_edit_agent_success(mock_edit_file, unpage, test_profile, test_agent_file):
    """Test successful agent editing.

    Should:
    - Find existing agent file
    - Call edit_file() with agent file path and editor
    - Exit with code 0 (success)
    """
    mock_edit_file.return_value = None

    # Verify agent file exists
    agent_file = test_profile / "agents" / "test-agent.yaml"
    assert agent_file.exists()

    # Run the command
    stdout, stderr, exit_code = unpage("agent edit test-agent")

    # Verify success and exit code
    assert stderr == ""
    assert exit_code == 0

    # Verify edit_file was called with correct path
    mock_edit_file.assert_called_once_with(agent_file, None)


@patch("unpage.cli.agent.edit.edit_file")
def test_edit_default_agent_creates_if_missing(mock_edit_file, unpage, test_profile):
    """Test editing default agent creates it if missing.

    Should:
    - Create default agent file if it doesn't exist
    - Call edit_file() with agent file path
    - Exit with code 0 (success)
    """
    mock_edit_file.return_value = None

    # Ensure default agent doesn't exist initially
    agents_dir = test_profile / "agents"
    agents_dir.mkdir(exist_ok=True)
    default_agent_file = agents_dir / "default.yaml"
    assert not default_agent_file.exists()

    # Run the command for default agent
    stdout, stderr, exit_code = unpage("agent edit default")

    # Verify success and exit code
    assert stderr == ""
    assert exit_code == 0

    # Verify default agent file was created
    assert default_agent_file.exists()

    # Verify edit_file was called
    mock_edit_file.assert_called_once_with(default_agent_file, None)


def test_edit_nonexistent_agent(unpage, test_profile):
    """Test editing agent that doesn't exist.

    Should:
    - Show error message when agent file not found
    - Exit with code 1 (error)
    """
    # Ensure agent doesn't exist
    agent_file = test_profile / "agents" / "nonexistent.yaml"
    assert not agent_file.exists()

    # Run the command for non-existent agent
    stdout, stderr, exit_code = unpage("agent edit nonexistent")

    # Verify error message and exit code
    assert "Agent 'nonexistent' not found" in stdout
    assert "Use 'unpage agent create nonexistent' to create" in stdout
    assert stderr == ""
    assert exit_code == 1


@patch("unpage.cli.agent.edit.edit_file")
def test_edit_agent_no_editor(mock_edit_file, unpage, test_profile, test_agent_file, no_editor):
    """Test editing agent when no editor is available.

    Should:
    - Find existing agent file
    - Handle ValueError from edit_file() when no editor specified
    - Exit with code 1 (error) when editor fails
    """
    mock_edit_file.side_effect = ValueError("No editor specified")

    # Verify agent file exists
    agent_file = test_profile / "agents" / "test-agent.yaml"
    assert agent_file.exists()

    # Run the command
    stdout, stderr, exit_code = unpage("agent edit test-agent")

    # Verify error message and exit code
    assert "No editor specified" in stdout
    assert "manually open" in stdout
    assert stderr == ""
    assert exit_code == 1

    # Verify edit_file was called and failed
    mock_edit_file.assert_called_once()


@patch("unpage.cli.agent.edit.edit_file")
def test_edit_agent_with_custom_editor(mock_edit_file, unpage, test_profile, test_agent_file):
    """Test editing agent with explicit editor parameter.

    Should:
    - Use the specified editor instead of environment variable
    - Call edit_file() with the custom editor
    - Exit with code 0 (success)
    """
    mock_edit_file.return_value = None

    # Run the command with explicit editor
    stdout, stderr, exit_code = unpage("agent edit test-agent --editor nano")

    # Verify success and exit code
    assert stderr == ""
    assert exit_code == 0

    # Verify edit_file was called with custom editor
    agent_file = test_profile / "agents" / "test-agent.yaml"
    mock_edit_file.assert_called_once_with(agent_file, "nano")
