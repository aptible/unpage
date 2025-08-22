"""Tests for the profile use CLI command."""


def test_use_profile_success(unpage, isolated_config_dir, mock_config_manager):
    """Test successful profile switching.

    Should:
    - Check if profile exists in filesystem
    - Switch to the provided profile name
    - Exit with code 0 (success)
    """
    # Create staging profile
    profiles_dir = isolated_config_dir / "profiles"
    staging_dir = profiles_dir / "staging"
    staging_dir.mkdir(parents=True)
    (staging_dir / "config.yaml").write_text("plugins: {}\n")

    # Start with a different active profile
    mock_config_manager.set_active_profile("test")

    # Run the command
    stdout, stderr, exit_code = unpage("profile use staging")

    # Verify success message and exit code
    assert "Switched to profile 'staging'" in stdout
    assert stderr == ""
    assert exit_code == 0

    # Verify active profile actually changed
    assert mock_config_manager.get_active_profile() == "staging"


def test_use_nonexistent_profile(unpage, isolated_config_dir, mock_config_manager):
    """Test switching to profile that doesn't exist.

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

    # Store original active profile
    original_profile = mock_config_manager.get_active_profile()

    # Run the command with non-existent profile
    stdout, stderr, exit_code = unpage("profile use nonexistent")

    # Verify error message and exit code
    assert "Profile 'nonexistent' does not exist!" in stdout
    assert "Available profiles:" in stdout
    # Check that existing profiles are listed in the error message
    assert "staging" in stdout
    assert stderr == ""
    assert exit_code == 1

    # Verify active profile didn't change
    assert mock_config_manager.get_active_profile() == original_profile
