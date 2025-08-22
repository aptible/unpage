"""Tests for the agent list CLI command."""


def test_list_agents_success(unpage, test_profile):
    """Test successful agent listing with real agent files."""
    # Create multiple agent files
    agents_dir = test_profile / "agents"
    agents_dir.mkdir()

    agent_names = ["incident-responder", "log-analyzer", "test-agent"]
    for name in agent_names:
        agent_content = f"""description: {name} agent
prompt: You are a {name}.
tools:
  - "*"
"""
        (agents_dir / f"{name}.yaml").write_text(agent_content)

    stdout, stderr, exit_code = unpage("agent list")

    assert "Available agents:" in stdout
    # Should include default agent plus created agents
    assert "* default" in stdout
    for agent in agent_names:
        assert f"* {agent}" in stdout
    assert stderr == ""
    assert exit_code == 0


def test_list_agents_includes_default(unpage, test_profile):
    """Test agent listing always includes default agent."""
    # Don't create any agent files, should still show default
    stdout, stderr, exit_code = unpage("agent list")

    assert "Available agents:" in stdout
    assert "* default" in stdout
    assert stderr == ""
    assert exit_code == 0


def test_list_agents_empty_directory(unpage, test_profile):
    """Test agent listing when agents directory doesn't exist."""
    # Don't create agents directory at all
    stdout, stderr, exit_code = unpage("agent list")

    assert "Available agents:" in stdout
    assert "* default" in stdout
    assert stderr == ""
    assert exit_code == 0
