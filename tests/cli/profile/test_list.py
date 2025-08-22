"""Tests for the profile list CLI command."""


def test_list_profiles_shows_available_profiles(unpage, isolated_config_dir, mock_config_manager):
    """Test that list command shows all available profiles.

    Should:
    - Display all available profiles from filesystem
    - Show active profile with indicator
    - Exit with code 0 (success)
    """
    # Create multiple profiles
    profiles_dir = isolated_config_dir / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)

    profile_names = ["default", "staging", "production"]
    for name in profile_names:
        profile_dir = profiles_dir / name
        profile_dir.mkdir(exist_ok=True)
        # Create a minimal config.yaml file to make the profile valid
        (profile_dir / "config.yaml").write_text("plugins: {}\n")

    # Set active profile to default using the config manager
    mock_config_manager.set_active_profile("default")

    # Run the command
    stdout, stderr, exit_code = unpage("profile list")

    # Verify all profiles appear in output
    assert "Available profiles:" in stdout
    for profile in profile_names:
        assert profile in stdout

    # Verify success
    assert stderr == ""
    assert exit_code == 0


def test_list_profiles_identifies_active_profile(unpage, isolated_config_dir, mock_config_manager):
    """Test that list command identifies the active profile.

    Should:
    - Distinguish active profile from inactive ones in output
    - Show active profile with special marker
    - Exit with code 0 (success)
    """
    # Create multiple profiles
    profiles_dir = isolated_config_dir / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)

    profile_names = ["default", "staging", "production"]
    for name in profile_names:
        profile_dir = profiles_dir / name
        profile_dir.mkdir(exist_ok=True)
        # Create a minimal config.yaml file to make the profile valid
        (profile_dir / "config.yaml").write_text("plugins: {}\n")

    # Set active profile to staging using the config manager
    mock_config_manager.set_active_profile("staging")

    # Run the command
    stdout, stderr, exit_code = unpage("profile list")

    # Verify active profile is marked specially
    assert "* staging" in stdout and "(active)" in stdout
    # Verify non-active profiles are not marked as active
    lines = stdout.split("\n")
    staging_line = next((line for line in lines if "staging" in line), "")
    default_line = next((line for line in lines if "default" in line and "staging" not in line), "")
    production_line = next((line for line in lines if "production" in line), "")

    assert "(active)" in staging_line
    assert "(active)" not in default_line
    assert "(active)" not in production_line

    # Verify success
    assert stderr == ""
    assert exit_code == 0
