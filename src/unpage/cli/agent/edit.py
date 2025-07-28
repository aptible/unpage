import asyncio

import typer
from rich import print

from unpage.agent.utils import get_agent_template
from unpage.cli.agent._app import agent_app
from unpage.cli.options import PROFILE_OPTION
from unpage.config.utils import get_config_dir
from unpage.utils import edit_file, get_editor


@agent_app.command()
def edit(
    agent_name: str = typer.Argument(..., help="The name of the agent to edit"),
    profile: str = PROFILE_OPTION,
    editor: str = typer.Option(
        get_editor(),
        help="The editor to use to open the agent file; DAYDREAM_EDITOR and EDITOR environment variables also work",
    ),
) -> None:
    """Edit an existing agent configuration file."""

    async def _edit() -> None:
        # Get the config directory for the profile
        config_dir = get_config_dir(profile, create=False)

        # Build the agent file path
        agent_file = config_dir / "agents" / f"{agent_name}.yaml"

        # If they're editing the default agent and it doesn't exist, create it.
        if agent_name == "default" and not agent_file.exists():
            agent_file = config_dir / "agents" / "default.yaml"
            agent_file.parent.mkdir(parents=True, exist_ok=True)
            agent_file.touch()
            agent_file.write_text(get_agent_template(agent_name))

        # Check if the agent file exists
        if not agent_file.exists():
            print(f"Agent '{agent_name}' not found at {agent_file}")
            print(f"Use 'unpage agent create {agent_name}' to create a new agent.")
            raise typer.Abort()

        # Open the file in the user's editor
        try:
            await edit_file(agent_file, editor)
        except ValueError as ex:
            print(
                "[red]No editor specified. Set the $EDITOR environment variable or use --editor option.[/red]"
            )
            print(f"[blue]Please manually open {str(agent_file)!r} in your editor.[/blue]")
            raise typer.Exit() from ex

    asyncio.run(_edit())
