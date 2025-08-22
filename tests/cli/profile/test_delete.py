"""Tests for the profile delete CLI command."""

from unittest.mock import patch


def test_delete_profile_success(unpage, isolated_config_dir, mock_config_manager):
    """Test successful profile deletion.

    Should:
    - Delete actual profile directory and files
    - Complete deletion when profile exists and is not active
    - Exit with code 0 (success)
    """
    # Create a profile to delete
    profiles_dir = isolated_config_dir / "profiles"
    staging_dir = profiles_dir / "staging"
    staging_dir.mkdir(parents=True)
    (staging_dir / "config.yaml").write_text("plugins: {}\n")

    # Set active profile to something different than what we're deleting
    mock_config_manager.set_active_profile("test")

    # Run the command with force to skip confirmation
    stdout, stderr, exit_code = unpage("profile delete staging --force")

    # Verify success message and exit code
    assert "Profile 'staging' deleted successfully" in stdout
    assert stderr == ""
    assert exit_code == 0

    # Verify actual profile directory was deleted
    assert not staging_dir.exists()


def test_delete_nonexistent_profile(unpage, isolated_config_dir, mock_config_manager):
    """Test deletion of profile that doesn't exist.

    Should:
    - Check if profile exists in filesystem
    - Exit with code 1 (error) if profile not found
    """
    # Create some existing profiles
    profiles_dir = isolated_config_dir / "profiles"
    for name in ["default", "staging"]:
        profile_dir = profiles_dir / name
        profile_dir.mkdir(parents=True, exist_ok=True)
        (profile_dir / "config.yaml").write_text("plugins: {}\n")

    # Run the command with nonexistent profile
    stdout, stderr, exit_code = unpage("profile delete nonexistent")

    # Verify error message and exit code
    assert "Profile 'nonexistent' does not exist" in stdout
    assert "Available profiles:" in stdout
    # Check that existing profiles are listed in the error message
    assert "staging" in stdout
    assert stderr == ""
    assert exit_code == 1


def test_delete_default_profile(unpage, isolated_config_dir, mock_config_manager):
    """Test deletion of default profile (should be prevented).

    Should:
    - Prevent deletion of 'default' profile
    - Exit with code 1 (error)
    """
    # Create default profile
    profiles_dir = isolated_config_dir / "profiles"
    default_dir = profiles_dir / "default"
    default_dir.mkdir(parents=True, exist_ok=True)
    (default_dir / "config.yaml").write_text("plugins: {}\n")

    # Run the command
    stdout, stderr, exit_code = unpage("profile delete default")

    # Verify error message and exit code
    assert "Cannot delete the default profile" in stdout
    assert stderr == ""
    assert exit_code == 1

    # Verify default profile still exists
    assert default_dir.exists()


def test_delete_active_profile_without_force(unpage, isolated_config_dir, mock_config_manager):
    """Test deletion of active profile without force flag.

    Should:
    - Check if profile is active
    - Exit with code 1 (error) when profile is active and force=False
    """
    # Create staging profile
    profiles_dir = isolated_config_dir / "profiles"
    staging_dir = profiles_dir / "staging"
    staging_dir.mkdir(parents=True)
    (staging_dir / "config.yaml").write_text("plugins: {}\n")

    # Set staging as the active profile
    mock_config_manager.set_active_profile("staging")

    # Run the command without force
    stdout, stderr, exit_code = unpage("profile delete staging")

    # Verify error message and exit code
    assert "Cannot delete active profile 'staging'" in stdout
    assert "Use --force or switch to a different" in stdout and "profile first" in stdout
    assert stderr == ""
    assert exit_code == 1

    # Verify profile still exists
    assert staging_dir.exists()


def test_delete_active_profile_with_force(unpage, isolated_config_dir, mock_config_manager):
    """Test deletion of active profile with force flag.

    Should:
    - Allow deletion when force=True even if profile is active
    - Switch to default profile after deletion
    - Exit with code 0 (success)
    """
    # Create staging and default profiles
    profiles_dir = isolated_config_dir / "profiles"
    staging_dir = profiles_dir / "staging"
    staging_dir.mkdir(parents=True)
    (staging_dir / "config.yaml").write_text("plugins: {}\n")

    default_dir = profiles_dir / "default"
    default_dir.mkdir(parents=True, exist_ok=True)
    (default_dir / "config.yaml").write_text("plugins: {}\n")

    # Set staging as the active profile
    mock_config_manager.set_active_profile("staging")

    # Run the command with force
    stdout, stderr, exit_code = unpage("profile delete staging --force")

    # Verify success messages and exit code
    assert "Profile 'staging' deleted successfully" in stdout
    assert "Switched to profile 'default'" in stdout
    assert stderr == ""
    assert exit_code == 0

    # Verify staging profile was deleted
    assert not staging_dir.exists()
    # Verify default profile still exists
    assert default_dir.exists()
    # Verify active profile switched to default
    assert mock_config_manager.get_active_profile() == "default"


@patch("unpage.cli.profile.delete.confirm")
def test_delete_profile_user_confirms(
    mock_confirm, unpage, isolated_config_dir, mock_config_manager
):
    """Test profile deletion when user confirms the prompt.

    Should:
    - Prompt for confirmation when force=False
    - Proceed with deletion when user confirms
    - Exit with code 0 (success)
    """
    # Create staging profile
    profiles_dir = isolated_config_dir / "profiles"
    staging_dir = profiles_dir / "staging"
    staging_dir.mkdir(parents=True)
    (staging_dir / "config.yaml").write_text("plugins: {}\n")

    # Set active profile to something different than what we're deleting
    mock_config_manager.set_active_profile("test")

    # Mock user confirmation - user says yes
    mock_confirm.return_value = True

    # Run the command without force (should prompt)
    stdout, stderr, exit_code = unpage("profile delete staging")

    # Verify success message and exit code
    assert "Profile 'staging' deleted successfully" in stdout
    assert stderr == ""
    assert exit_code == 0

    # Verify confirmation was asked and deletion actually happened
    mock_confirm.assert_called_once()
    assert not staging_dir.exists()


@patch("unpage.cli.profile.delete.confirm")
def test_delete_profile_user_declines(
    mock_confirm, unpage, isolated_config_dir, mock_config_manager
):
    """Test profile deletion when user declines the prompt.

    Should:
    - Prompt for confirmation when force=False
    - Exit with code 0 (success) when user declines (not an error)
    """
    # Create staging profile
    profiles_dir = isolated_config_dir / "profiles"
    staging_dir = profiles_dir / "staging"
    staging_dir.mkdir(parents=True)
    (staging_dir / "config.yaml").write_text("plugins: {}\n")

    # Set active profile to something different than what we're deleting
    mock_config_manager.set_active_profile("test")

    # Mock user confirmation - user says no
    mock_confirm.return_value = False

    # Run the command without force (should prompt)
    stdout, stderr, exit_code = unpage("profile delete staging")

    # Verify cancellation message and exit code
    assert "Deletion cancelled" in stdout
    assert stderr == ""
    assert exit_code == 0  # Not an error when user cancels

    # Verify confirmation was asked but no deletion occurred
    mock_confirm.assert_called_once()
    assert staging_dir.exists()  # Profile should still exist
