import sys

import rich

from unpage.agent.utils import delete_agent
from unpage.cli.agent._app import agent_app
from unpage.config import manager
from unpage.telemetry import client as telemetry
from unpage.telemetry import hash_value, prepare_profile_for_telemetry


@agent_app.command
async def delete(agent_name: str) -> None:
    """Delete an agent.

    Parameters
    ----------
    agent_name
        The name of the agent to delete
    """
    await telemetry.send_event(
        {
            "command": "agent delete",
            "agent_name_sha256": hash_value(agent_name),
            **prepare_profile_for_telemetry(manager.get_active_profile()),
        }
    )
    try:
        delete_agent(agent_name)
        rich.print(f"[green]Agent '{agent_name}' deleted successfully[/green]")
    except FileNotFoundError:
        rich.print(f"[red]Agent '{agent_name}' does not exist[/red]")
        sys.exit(1)
