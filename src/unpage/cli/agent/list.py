from rich import print

from unpage.agent.utils import get_agents
from unpage.cli.agent._app import agent_app
from unpage.config import manager
from unpage.telemetry import client as telemetry
from unpage.telemetry import prepare_profile_for_telemetry


@agent_app.command
async def list() -> None:
    """List the available agents."""
    await telemetry.send_event(
        {
            "command": "agent list",
            **prepare_profile_for_telemetry(manager.get_active_profile()),
        }
    )
    print("Available agents:")
    for agent in sorted(get_agents()):
        print(f"* {agent}")
