"""Tests for the agent schedule CLI command."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_yaml import parse_yaml_raw_as

from unpage.agent.analysis import Agent
from unpage.agent.scheduler import AgentScheduler


@pytest.fixture
def scheduled_agent_yaml() -> str:
    """Return a sample scheduled agent YAML configuration."""
    return """
description: Run monthly cost optimization checks
schedule:
  cron: "0 10 2 * *"
prompt: >
  Analyze infrastructure costs and identify optimization opportunities.
tools:
  - "aws_*"
  - "graph_*"
"""


@pytest.fixture
def agent_without_schedule_yaml() -> str:
    """Return a sample agent YAML configuration without a schedule."""
    return """
description: Investigate high CPU usage alerts
prompt: >
  Investigate the cause of high CPU usage.
tools:
  - "aws_*"
"""


def test_agent_schedule_field_parses(scheduled_agent_yaml: str) -> None:
    """Test that the schedule field is parsed correctly from YAML."""
    agent = parse_yaml_raw_as(Agent, scheduled_agent_yaml)
    assert agent.schedule is not None
    assert agent.schedule.cron == "0 10 2 * *"


def test_agent_without_schedule_parses(agent_without_schedule_yaml: str) -> None:
    """Test that agents without schedules still parse correctly."""
    agent = parse_yaml_raw_as(Agent, agent_without_schedule_yaml)
    assert agent.schedule is None


@pytest.mark.asyncio
async def test_scheduler_loads_scheduled_agents(
    tmp_path: Path, scheduled_agent_yaml: str, agent_without_schedule_yaml: str
) -> None:
    """Test that the scheduler loads only agents with schedules."""
    # Create a temporary agents directory
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()

    # Create two agent files
    (agents_dir / "cost-optimizer.yaml").write_text(scheduled_agent_yaml)
    (agents_dir / "cpu-investigator.yaml").write_text(agent_without_schedule_yaml)

    with (
        patch("unpage.agent.utils.manager.get_active_profile_directory", return_value=tmp_path),
        patch("unpage.agent.utils.manager.get_active_profile", return_value="test"),
    ):
        scheduler = AgentScheduler()
        scheduler.load_scheduled_agents()

        # Only the scheduled agent should be loaded
        assert len(scheduler.scheduled_agents) == 1
        assert "cost-optimizer" in scheduler.scheduled_agents
        assert "cpu-investigator" not in scheduler.scheduled_agents


@pytest.mark.asyncio
async def test_scheduler_setup_jobs(tmp_path: Path, scheduled_agent_yaml: str) -> None:
    """Test that the scheduler sets up jobs correctly."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "test-agent.yaml").write_text(scheduled_agent_yaml)

    with (
        patch("unpage.agent.utils.manager.get_active_profile_directory", return_value=tmp_path),
        patch("unpage.agent.utils.manager.get_active_profile", return_value="test"),
    ):
        scheduler = AgentScheduler()
        scheduler.load_scheduled_agents()
        scheduler.setup_jobs()

        # Check that a job was added to the scheduler
        jobs = scheduler.scheduler.get_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == "test-agent"
        assert jobs[0].name == "Agent: test-agent"


@pytest.mark.asyncio
async def test_run_scheduled_agent(tmp_path: Path, scheduled_agent_yaml: str) -> None:
    """Test that scheduled agents can be executed."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "test-agent.yaml").write_text(scheduled_agent_yaml)

    with (
        patch("unpage.agent.utils.manager.get_active_profile_directory", return_value=tmp_path),
        patch("unpage.agent.utils.manager.get_active_profile", return_value="test"),
        patch("unpage.agent.scheduler.AnalysisAgent") as mock_analysis_agent,
    ):
        # Mock the analysis agent's acall method
        mock_instance = AsyncMock()
        mock_instance.acall = AsyncMock(return_value="Analysis complete")
        mock_analysis_agent.return_value = mock_instance

        scheduler = AgentScheduler()
        scheduler.load_scheduled_agents()

        # Run the scheduled agent
        await scheduler.run_scheduled_agent("test-agent")

        # Verify that the analysis agent was called with an empty payload
        mock_instance.acall.assert_called_once()
        call_kwargs = mock_instance.acall.call_args.kwargs
        assert call_kwargs["payload"] == ""
        assert call_kwargs["agent"].name == "test-agent"


@pytest.mark.asyncio
async def test_scheduler_with_no_agents(tmp_path: Path) -> None:
    """Test that the scheduler handles the case with no scheduled agents."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()

    with (
        patch("unpage.agent.utils.manager.get_active_profile_directory", return_value=tmp_path),
        patch("unpage.agent.utils.manager.get_active_profile", return_value="test"),
    ):
        scheduler = AgentScheduler()
        scheduler.load_scheduled_agents()

        # No agents should be loaded
        assert len(scheduler.scheduled_agents) == 0


@pytest.mark.asyncio
async def test_scheduler_with_invalid_cron(tmp_path: Path) -> None:
    """Test that the scheduler handles invalid cron expressions gracefully."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()

    invalid_yaml = """
description: Test agent with invalid cron
schedule:
  cron: "invalid cron expression"
prompt: Test prompt
tools:
  - "core_*"
"""
    (agents_dir / "invalid-agent.yaml").write_text(invalid_yaml)

    with (
        patch("unpage.agent.utils.manager.get_active_profile_directory", return_value=tmp_path),
        patch("unpage.agent.utils.manager.get_active_profile", return_value="test"),
    ):
        scheduler = AgentScheduler()
        scheduler.load_scheduled_agents()

        # Agent should be loaded despite invalid cron
        assert len(scheduler.scheduled_agents) == 1

        # But setting up jobs should fail gracefully
        scheduler.setup_jobs()

        # No jobs should be created due to invalid cron
        jobs = scheduler.scheduler.get_jobs()
        assert len(jobs) == 0
