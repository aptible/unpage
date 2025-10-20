"""CLI command for running the agent scheduler."""

from unpage.agent.scheduler import AgentScheduler
from unpage.cli.agent._app import agent_app
from unpage.config import manager
from unpage.telemetry import client as telemetry
from unpage.telemetry import prepare_profile_for_telemetry


@agent_app.command
async def schedule() -> None:
    """Start the agent scheduler to run agents on a periodic schedule.

    The scheduler will load all agents that have a 'schedule' configuration
    in their YAML files and run them according to their cron expressions.

    Agents will run with no input payload, so make sure your agent prompts
    specify how to get any required inputs (e.g., via tool calls).

    Example agent configuration:

        description: Run monthly cost optimization checks
        schedule:
          cron: "0 10 2 * *"  # 10am on the 2nd of every month
        prompt: >
          Analyze infrastructure costs and identify optimization opportunities.
          Use available tools to get cost data and generate recommendations.
        tools:
          - "aws_*"
          - "graph_*"

    Press Ctrl+C to stop the scheduler.
    """
    await telemetry.send_event(
        {
            "command": "agent schedule",
            **prepare_profile_for_telemetry(manager.get_active_profile()),
        }
    )

    scheduler = AgentScheduler()
    await scheduler.start()
