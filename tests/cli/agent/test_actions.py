"""Tests for the agent actions utilities."""

import pytest
from pathlib import Path
from unittest.mock import patch

from unpage.cli.agent.actions import create_agent


@pytest.mark.asyncio
@patch("unpage.cli.agent.actions.confirm")
@patch("unpage.cli.agent.actions.manager.get_active_profile_directory")
@patch("unpage.cli.agent.actions.get_agent_template")
async def test_create_agent_success(mock_get_template, mock_get_dir, mock_confirm):
    """Test successful agent creation.

    Should:
    - Get agent template content
    - Create agents directory if needed
    - Write template to agent file
    - Return path to created file
    """
    # Setup mocks
    mock_get_template.return_value = "# Test agent template\nname: test"
    mock_config_dir = Path("/fake/config")
    mock_get_dir.return_value = mock_config_dir

    # Mock the file system operations
    with (
        patch("pathlib.Path.mkdir") as mock_mkdir,
        patch("pathlib.Path.exists", return_value=False) as mock_exists,
        patch("pathlib.Path.write_text") as mock_write,
    ):
        # Run the function
        result = await create_agent("test-agent", overwrite=False, template="default")

        # Verify the result
        expected_path = mock_config_dir / "agents" / "test-agent.yaml"
        assert result == expected_path

        # Verify template was fetched
        mock_get_template.assert_called_once_with("default")

        # Verify directory creation
        mock_mkdir.assert_called_once_with(exist_ok=True)

        # Verify file was written
        mock_write.assert_called_once_with("# Test agent template\nname: test", encoding="utf-8")


@pytest.mark.asyncio
@patch("unpage.cli.agent.actions.manager.get_active_profile_directory")
@patch("unpage.cli.agent.actions.get_agent_template")
async def test_create_agent_invalid_template(mock_get_template, mock_get_dir):
    """Test agent creation with invalid template.

    Should:
    - Raise FileNotFoundError when template doesn't exist
    - Exit with code 1
    """
    # Setup mocks
    mock_get_template.side_effect = FileNotFoundError("Template not found")
    mock_config_dir = Path("/fake/config")
    mock_get_dir.return_value = mock_config_dir

    # Test that SystemExit is raised with code 1
    with pytest.raises(SystemExit) as exc_info:
        await create_agent("test-agent", overwrite=False, template="invalid")

    assert exc_info.value.code == 1
    mock_get_template.assert_called_once_with("invalid")


@pytest.mark.asyncio
@patch("unpage.cli.agent.actions.confirm")
@patch("unpage.cli.agent.actions.manager.get_active_profile_directory")
@patch("unpage.cli.agent.actions.get_agent_template")
async def test_create_agent_with_overwrite(mock_get_template, mock_get_dir, mock_confirm):
    """Test agent creation with overwrite flag when file exists.

    Should:
    - Skip confirmation when overwrite=True
    - Overwrite existing file
    - Return path to created file
    """
    # Setup mocks
    mock_get_template.return_value = "# Test agent template\nname: test"
    mock_config_dir = Path("/fake/config")
    mock_get_dir.return_value = mock_config_dir

    # Mock the file system operations - file exists
    with (
        patch("pathlib.Path.mkdir") as mock_mkdir,
        patch("pathlib.Path.exists", return_value=True) as mock_exists,
        patch("pathlib.Path.write_text") as mock_write,
    ):
        # Run the function with overwrite=True
        result = await create_agent("test-agent", overwrite=True, template="default")

        # Verify the result
        expected_path = mock_config_dir / "agents" / "test-agent.yaml"
        assert result == expected_path

        # Verify confirmation was NOT called (overwrite=True)
        mock_confirm.assert_not_called()

        # Verify file was written
        mock_write.assert_called_once_with("# Test agent template\nname: test", encoding="utf-8")


@pytest.mark.asyncio
@patch("unpage.cli.agent.actions.confirm")
@patch("unpage.cli.agent.actions.manager.get_active_profile_directory")
@patch("unpage.cli.agent.actions.get_agent_template")
async def test_create_agent_exists_user_confirms(mock_get_template, mock_get_dir, mock_confirm):
    """Test agent creation when file exists and user confirms.

    Should:
    - Prompt for confirmation when file exists and overwrite=False
    - Proceed with creation when user confirms
    - Return path to created file
    """
    # Setup mocks
    mock_get_template.return_value = "# Test agent template\nname: test"
    mock_config_dir = Path("/fake/config")
    mock_get_dir.return_value = mock_config_dir
    mock_confirm.return_value = True  # User confirms

    # Mock the file system operations - file exists
    with (
        patch("pathlib.Path.mkdir") as mock_mkdir,
        patch("pathlib.Path.exists", return_value=True) as mock_exists,
        patch("pathlib.Path.write_text") as mock_write,
    ):
        # Run the function
        result = await create_agent("test-agent", overwrite=False, template="default")

        # Verify the result
        expected_path = mock_config_dir / "agents" / "test-agent.yaml"
        assert result == expected_path

        # Verify confirmation was called
        mock_confirm.assert_called_once_with("Do you want to overwrite it?")

        # Verify file was written
        mock_write.assert_called_once_with("# Test agent template\nname: test", encoding="utf-8")


@pytest.mark.asyncio
@patch("unpage.cli.agent.actions.confirm")
@patch("unpage.cli.agent.actions.manager.get_active_profile_directory")
@patch("unpage.cli.agent.actions.get_agent_template")
async def test_create_agent_exists_user_declines(mock_get_template, mock_get_dir, mock_confirm):
    """Test agent creation when file exists and user declines.

    Should:
    - Prompt for confirmation when file exists and overwrite=False
    - Exit with code 1 when user declines
    """
    # Setup mocks
    mock_get_template.return_value = "# Test agent template\nname: test"
    mock_config_dir = Path("/fake/config")
    mock_get_dir.return_value = mock_config_dir
    mock_confirm.return_value = False  # User declines

    # Mock the file system operations - file exists
    with (
        patch("pathlib.Path.mkdir") as mock_mkdir,
        patch("pathlib.Path.exists", return_value=True) as mock_exists,
        patch("pathlib.Path.write_text") as mock_write,
    ):
        # Test that SystemExit is raised with code 1
        with pytest.raises(SystemExit) as exc_info:
            await create_agent("test-agent", overwrite=False, template="default")

        assert exc_info.value.code == 1

        # Verify confirmation was called
        mock_confirm.assert_called_once_with("Do you want to overwrite it?")

        # Verify file was NOT written
        mock_write.assert_not_called()
