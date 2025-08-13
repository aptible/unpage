"""Tests for the profile create CLI command."""


def test_create_profile_success(unpage, isolated_config_dir):
    """Test successful profile creation.

    Should:
    - Create actual profile directory and files
    - Complete without errors when profile doesn't exist
    - Exit with code 0 (success)
    """
    # Run the command
    stdout, stderr, exit_code = unpage("profile create test-profile")

    # Verify success message and exit code
    assert "Profile 'test-profile' created successfully!" in stdout
    assert stderr == ""
    assert exit_code == 0

    # Verify actual profile directory was created
    profile_dir = isolated_config_dir / "profiles" / "test-profile"
    assert profile_dir.exists()
    assert profile_dir.is_dir()


def test_create_profile_already_exists(unpage, isolated_config_dir):
    """Test profile creation when profile already exists.

    Should:
    - Handle FileExistsError when profile directory exists
    - Exit with code 1 (error) when profile already exists
    """
    # Create a profile directory that already exists
    profile_dir = isolated_config_dir / "profiles" / "existing-profile"
    profile_dir.mkdir(parents=True)

    # Run the command
    stdout, stderr, exit_code = unpage("profile create existing-profile")

    # Verify error message and exit code
    assert "Profile 'existing-profile' already exists!" in stdout
    assert stderr == ""
    assert exit_code == 1
