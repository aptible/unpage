import anyio
from rich import print

from unpage.agent.utils import get_agent_templates
from unpage.cli.agent._app import agent_app
from unpage.telemetry import client as telemetry


@agent_app.command()
def templates() -> None:
    """List the available agent templates."""

    async def _run() -> None:
        await telemetry.send_event(
            {
                "command": "agent templates",
            }
        )
        print("Available agent templates:")
        for template in sorted(get_agent_templates()):
            print(f"* {template}")

    anyio.run(_run)
