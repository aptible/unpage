"""Tests for the agent create CLI command."""

from unittest.mock import patch


@patch("unpage.cli.agent.create.edit_file")
def test_create_agent_success(mock_edit_file, unpage, test_profile, monkeypatch):
    """Test successful agent creation."""
    mock_edit_file.return_value = None
    monkeypatch.setenv("EDITOR", "vim")

    stdout, stderr, exit_code = unpage("agent create test-agent")

    # The command should exit successfully.
    assert stderr == ""
    assert exit_code == 0

    # The agent file should be created.
    agent_file = test_profile / "agents" / "test-agent.yaml"
    assert agent_file.exists()

    # We should have attempted to open the file with the user's editor.
    mock_edit_file.assert_called_once_with(agent_file, None)


@patch("unpage.cli.agent.create.edit_file")
def test_create_agent_no_edit_flag(mock_edit_file, unpage, test_profile):
    """Test agent creation with no_edit flag."""
    stdout, stderr, exit_code = unpage("agent create test-agent --no-edit")

    # The agent file should be created.
    agent_file = test_profile / "agents" / "test-agent.yaml"
    assert agent_file.exists()

    # We should not have attempted to open the file with the user's editor.
    mock_edit_file.assert_not_called()

    # The command should exit successfully.
    assert stderr == ""
    assert exit_code == 0


@patch("unpage.cli.agent.create.edit_file")
def test_create_agent_no_editor_error(mock_edit_file, unpage, test_profile, no_editor):
    """Test agent creation when no editor is available."""
    mock_edit_file.side_effect = ValueError("No editor specified")

    stdout, stderr, exit_code = unpage("agent create test-agent")

    # The agent file should be created.
    agent_file = test_profile / "agents" / "test-agent.yaml"
    assert agent_file.exists()

    # We should have attempted to open the file with the user's $EDITOR.
    mock_edit_file.assert_called_once()

    # The command should exit with an error mentioning that we couldn't find an
    # editor, and that the user should manually edit the file.
    assert exit_code == 1
    assert "No editor specified" in stderr
    assert "manually open" in stderr


def test_create_agent_invalid_template(unpage, test_profile):
    """Test agent creation with invalid template."""
    stdout, stderr, exit_code = unpage("agent create test-agent --template nonexistent --no-edit")

    assert "template 'nonexistent' not found" in stderr.lower()

    # The agent file should not be created.
    agent_file = test_profile / "agents" / "test-agent.yaml"
    assert not agent_file.exists()

    # The command should exit with an error.
    assert exit_code == 1


@patch("unpage.cli.agent.create.edit_file")
def test_create_agent_with_overwrite(
    mock_edit_file, unpage, test_profile, test_agent_file, monkeypatch
):
    """Test agent creation with overwrite flag when file exists."""
    mock_edit_file.return_value = None
    monkeypatch.setenv("EDITOR", "vim")

    agent_file = test_profile / "agents" / "test-agent.yaml"
    assert agent_file.exists()

    # Capture timestamp before overwrite
    original_mtime = agent_file.stat().st_mtime

    stdout, stderr, exit_code = unpage("agent create test-agent --overwrite")

    # Verify file was actually overwritten (timestamp changed)
    assert agent_file.exists()
    new_mtime = agent_file.stat().st_mtime
    assert new_mtime > original_mtime

    # We should have attempted to open the file with the user's $EDITOR.
    mock_edit_file.assert_called_once_with(agent_file, None)

    # The command should exit successfully.
    assert stderr == ""
    assert exit_code == 0


@patch("unpage.cli.agent.actions.confirm")
@patch("unpage.cli.agent.create.edit_file")
def test_create_agent_exists_user_confirms(
    mock_edit_file, mock_confirm, unpage, test_profile, test_agent_file, monkeypatch
):
    """Test agent creation when file exists and user confirms overwrite."""
    mock_edit_file.return_value = None
    mock_confirm.return_value = True  # User confirms overwrite
    monkeypatch.setenv("EDITOR", "vim")

    stdout, stderr, exit_code = unpage("agent create test-agent")

    agent_file = test_profile / "agents" / "test-agent.yaml"
    assert agent_file.exists()

    mock_edit_file.assert_called_once_with(agent_file, None)
    mock_confirm.assert_called_once_with("Do you want to overwrite it?")

    assert stderr == ""
    assert exit_code == 0


@patch("unpage.cli.agent.actions.confirm")
@patch("unpage.cli.agent.create.edit_file")
def test_create_agent_exists_user_declines(
    mock_edit_file, mock_confirm, unpage, test_profile, test_agent_file
):
    """Test agent creation when file exists and user declines overwrite."""
    mock_confirm.return_value = False  # User declines overwrite

    stdout, stderr, exit_code = unpage("agent create test-agent")

    # We should have shown the "agent already exists" message.
    assert "already exists" in stdout

    # We should have asked the user if they want to overwrite the file.
    mock_confirm.assert_called_once_with("Do you want to overwrite it?")

    # We should not have attempted to open the file with the user's editor.
    mock_edit_file.assert_not_called()

    # The command should exit with an error since the user declined to
    # overwrite.
    assert exit_code == 1


@patch("unpage.cli.agent.create.edit_file")
def test_create_agent_editor_error(mock_edit_file, unpage, test_profile):
    """Test agent creation when editor fails to open."""
    mock_edit_file.side_effect = ValueError("No editor specified")

    stdout, stderr, exit_code = unpage("agent create test-agent --editor vim")

    # The agent file should be created.
    agent_file = test_profile / "agents" / "test-agent.yaml"
    assert agent_file.exists()

    # We should have attempted to open the file with the specified editor.
    mock_edit_file.assert_called_once_with(agent_file, "vim")

    # The command should exit with an error mentioning that we couldn't find an
    # editor, and that the user should manually edit the file.
    assert exit_code == 1
    assert "No editor specified" in stderr
    assert "manually open" in stderr
