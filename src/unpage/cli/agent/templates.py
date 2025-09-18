from rich import print
from rich.console import Console
from rich.table import Table

from unpage.agent.utils import get_agent_template_description, get_agent_templates
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
    table = Table("Template Name", "Description")
    for template in sorted(get_agent_templates()):
        table.add_row(template, get_agent_template_description(template).splitlines()[0])
    console = Console()
    console.print(table)
