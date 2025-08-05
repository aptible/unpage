from rich import print

from unpage.agent.utils import get_agent_templates
from unpage.cli.agent._app import agent_app
from unpage.telemetry import client as telemetry


@agent_app.command
async def templates() -> None:
    """List the available agent templates."""
    await telemetry.send_event(
        {
            "command": "agent templates",
        }
    )
    print("Available agent templates:")
    for template in sorted(get_agent_templates()):
        print(f"* {template}")
