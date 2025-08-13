"""Tests for the agent delete CLI command."""


def test_delete_agent_success(unpage, test_profile, test_agent_file):
    """Test successful agent deletion.

    Should:
    - Delete actual agent file
    - Show success message
    - Exit with code 0 (success)
    """
    # Verify agent file exists before deletion
    agent_file = test_profile / "agents" / "test-agent.yaml"
    assert agent_file.exists()

    # Run the command
    stdout, stderr, exit_code = unpage("agent delete test-agent")

    # Verify success message and exit code
    assert "Agent 'test-agent' deleted successfully" in stdout
    assert stderr == ""
    assert exit_code == 0

    # Verify agent file was actually deleted
    assert not agent_file.exists()


def test_delete_nonexistent_agent(unpage, test_profile):
    """Test deletion of agent that doesn't exist.

    Should:
    - Show error message when agent file not found
    - Exit with code 1 (error)
    """
    # Make sure agent doesn't exist
    agent_file = test_profile / "agents" / "nonexistent.yaml"
    assert not agent_file.exists()

    # Run the command
    stdout, stderr, exit_code = unpage("agent delete nonexistent")

    # Verify error message and exit code
    assert "Agent 'nonexistent' does not exist" in stdout
    assert stderr == ""
    assert exit_code == 1
