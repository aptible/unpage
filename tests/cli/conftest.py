"""Fixtures and utilities for CLI tests."""

import json
import os
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml


@pytest.fixture(autouse=True)
def isolated_config_dir(tmp_path, monkeypatch):
    """Automatically isolate all tests to use a temporary config directory.

    This ensures tests don't interfere with each other or the user's real config.
    """
    config_dir = tmp_path / "unpage_config"
    config_dir.mkdir()
    monkeypatch.setenv("UNPAGE_CONFIG_ROOT", str(config_dir))
    return config_dir


@pytest.fixture(autouse=True)
def mock_telemetry(monkeypatch):
    """Automatically disable telemetry for all tests."""

    async def noop(*args, **kwargs):
        pass

    monkeypatch.setattr("unpage.telemetry.client.send_event", noop)


# Removed autouse mock_interactive_prompts to allow targeted mocking in specific tests


@pytest.fixture(autouse=True)
def mock_config_manager(isolated_config_dir, monkeypatch):
    """Replace the global config manager with a test-isolated one."""
    from unpage.config import ConfigManager

    # Create a new config manager using our isolated directory
    test_manager = ConfigManager(config_root=isolated_config_dir)

    # Create and set the "test" profile as active
    if "test" not in test_manager.list_profiles():
        test_manager.create_profile("test")
    test_manager.set_active_profile("test")

    # Replace the global manager instance everywhere it's used
    monkeypatch.setattr("unpage.config.manager", test_manager)
    monkeypatch.setattr("unpage.cli.agent.create.manager", test_manager)
    monkeypatch.setattr("unpage.cli.agent.edit.manager", test_manager)
    monkeypatch.setattr("unpage.cli.agent.run.manager", test_manager)
    monkeypatch.setattr("unpage.cli.agent.delete.manager", test_manager)
    monkeypatch.setattr("unpage.agent.utils.manager", test_manager)
    monkeypatch.setattr("unpage.cli.agent.list.manager", test_manager)
    monkeypatch.setattr("unpage.cli.agent.delete.manager", test_manager)
    monkeypatch.setattr("unpage.cli.agent.actions.manager", test_manager)
    # Profile commands
    monkeypatch.setattr("unpage.cli.profile.create.manager", test_manager)
    monkeypatch.setattr("unpage.cli.profile.delete.manager", test_manager)
    monkeypatch.setattr("unpage.cli.profile.list.manager", test_manager)
    monkeypatch.setattr("unpage.cli.profile.use.manager", test_manager)
    # MCP commands
    monkeypatch.setattr("unpage.cli.mcp.start.manager", test_manager)
    monkeypatch.setattr("unpage.cli.mcp.tools.list.manager", test_manager)
    monkeypatch.setattr("unpage.cli.mcp.tools.call.manager", test_manager)
    # Graph commands
    monkeypatch.setattr("unpage.cli.graph.build.manager", test_manager)
    monkeypatch.setattr("unpage.cli.graph.status.manager", test_manager)
    monkeypatch.setattr("unpage.cli.graph.stop.manager", test_manager)
    monkeypatch.setattr("unpage.cli.graph.logs.manager", test_manager)
    # Graph background operations (CRITICAL for file path isolation)
    monkeypatch.setattr("unpage.cli.graph._background.manager", test_manager)

    return test_manager


@pytest.fixture
def unpage(isolated_config_dir):
    """Provide unpage CLI runner for executing commands in tests.

    Returns:
        Function that runs unpage commands and captures output
    """
    import shlex
    import sys
    from contextlib import redirect_stderr, redirect_stdout
    from io import StringIO
    from unittest.mock import patch

    def run_command(command_string: str) -> tuple[str, str, int]:
        """Run a unpage CLI command and capture its output.

        Args:
            command_string: Command like "version --json" or "profile list"

        Returns:
            tuple: (stdout, stderr, exit_code)
        """
        # Parse command into arguments
        args = shlex.split(command_string)

        # Capture stdout and stderr
        stdout_capture = StringIO()
        stderr_capture = StringIO()
        exit_code = 0

        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                # Import the main app
                from unpage.cli._app import app

                # Mock sys.argv to include our arguments
                with patch.object(sys, "argv", ["unpage", *args]):
                    try:
                        app(args)
                    except SystemExit as e:
                        # See https://github.com/python/typeshed/issues/8513#issue-1333671093
                        exit_code = 1 if isinstance(e.code, str) else e.code or 0
        except Exception as e:
            import traceback

            stderr_capture.write(f"Error: {e!s}\n")
            stderr_capture.write(f"Traceback:\n{traceback.format_exc()}\n")
            exit_code = 1

        return stdout_capture.getvalue(), stderr_capture.getvalue(), exit_code

    return run_command


@pytest.fixture
def test_profile(isolated_config_dir):
    """Create a test profile with minimal configuration."""
    profile_dir = isolated_config_dir / "profiles" / "test"
    profile_dir.mkdir(parents=True, exist_ok=True)

    config = {"plugins": {"aws": {"enabled": False}, "datadog": {"enabled": False}}}
    (profile_dir / "config.yaml").write_text(yaml.dump(config))

    # Set as active profile
    (isolated_config_dir / "config.yaml").write_text(yaml.dump({"active_profile": "test"}))
    return profile_dir


@pytest.fixture
def test_agent_file(test_profile):
    """Create a test agent configuration file."""
    agents_dir = test_profile / "agents"
    agents_dir.mkdir()

    agent_config = """description: Test agent for integration tests
prompt: You are a test agent.
tools:
  - "*"
"""
    agent_file = agents_dir / "test-agent.yaml"
    agent_file.write_text(agent_config)
    return agent_file


@pytest.fixture
def test_graph_data(test_profile):
    """Create test graph JSON data."""
    graph_data = {
        "nodes": [
            {"id": "ec2-1", "type": "EC2Instance", "name": "web-server"},
            {"id": "rds-1", "type": "RDSDatabase", "name": "postgres-db"},
        ],
        "edges": [{"from": "ec2-1", "to": "rds-1", "type": "connects_to"}],
    }
    graph_file = test_profile / "graph.json"
    graph_file.write_text(json.dumps(graph_data))
    return graph_file


@pytest.fixture
def mock_external_apis(monkeypatch):
    """Mock external API calls (AWS, Datadog, etc.)."""
    # Mock boto3 clients
    mock_ec2 = MagicMock()
    mock_ec2.describe_instances.return_value = {"Reservations": []}
    monkeypatch.setattr("boto3.client", lambda service, **kwargs: mock_ec2)

    return {"ec2": mock_ec2}


@pytest.fixture
def no_editor(monkeypatch):
    """Disable editor launching for tests."""
    monkeypatch.delenv("EDITOR", raising=False)
    monkeypatch.delenv("VISUAL", raising=False)
    monkeypatch.setattr("unpage.utils.get_editor", lambda: None)


@pytest.fixture
def mock_subprocess(monkeypatch):
    """Mock subprocess calls for background processes."""
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = "Success"
    mock_proc.stderr = ""

    def mock_run(*args, **kwargs):
        return mock_proc

    monkeypatch.setattr("subprocess.run", mock_run)
    monkeypatch.setattr("asyncio.create_subprocess_shell", AsyncMock(return_value=mock_proc))
    return mock_proc


@pytest.fixture
def test_templates(isolated_config_dir):
    """Create test agent templates."""
    templates_dir = isolated_config_dir / "templates"
    templates_dir.mkdir()

    default_template = """name: {{ agent_name }}
description: Default agent template
model: gpt-4
"""
    (templates_dir / "default.yaml").write_text(default_template)

    custom_template = """name: {{ agent_name }}
description: Custom agent template
model: claude-3
"""
    (templates_dir / "custom.yaml").write_text(custom_template)

    return templates_dir


@pytest.fixture
def running_graph_build(test_profile):
    """Simulate a running graph build process."""
    pid_file = test_profile / "graph_build.pid"
    pid_file.write_text(str(os.getpid()))

    log_file = test_profile / "graph_build.log"
    log_file.write_text("Building graph...\n")

    yield {"pid_file": pid_file, "log_file": log_file}

    # Cleanup
    pid_file.unlink(missing_ok=True)


@pytest.fixture
def mock_input(monkeypatch):
    """Mock user input for interactive prompts."""

    def make_input(*responses):
        responses_iter = iter(responses)
        monkeypatch.setattr("builtins.input", lambda _: next(responses_iter))
        return responses

    return make_input


@pytest.fixture
def mock_confirm_yes(monkeypatch):
    """Mock confirmation prompts to always return True."""

    async def confirm_yes(message, default=True):
        return True

    monkeypatch.setattr("unpage.utils.confirm", confirm_yes)


@pytest.fixture
def mock_confirm_no(monkeypatch):
    """Mock confirmation prompts to always return False."""

    async def confirm_no(message, default=True):
        return False

    monkeypatch.setattr("unpage.utils.confirm", confirm_no)


@pytest.fixture
def sample_profiles():
    """Sample profile data for tests.

    Returns:
        List of sample profile names for testing
    """
    return ["default", "staging", "production"]


@pytest.fixture
def sample_agents():
    """Sample agent data for tests.

    Returns:
        List of sample agent names for testing
    """
    return ["default", "incident-responder", "log-analyzer"]


# Temp config dir - keep for backward compatibility but point to isolated_config_dir
@pytest.fixture
def temp_config_dir(isolated_config_dir):
    """Legacy fixture name - points to isolated_config_dir."""
    return isolated_config_dir
