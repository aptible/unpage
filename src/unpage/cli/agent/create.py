import sys

from rich import print

from unpage.cli.agent._app import agent_app
from unpage.cli.agent.actions import create_agent
from unpage.config import manager
from unpage.telemetry import client as telemetry
from unpage.telemetry import hash_value, prepare_profile_for_telemetry
from unpage.utils import edit_file, get_editor


@agent_app.command
async def create(
    agent_name: str,
    /,
    *,
    overwrite: bool = False,
    template: str = "default",
    editor: str | None = get_editor(),
    no_edit: bool = False,
) -> None:
    """Create a new agent configuration file and open it in your editor.

    Parameters
    ----------
    agent_name
        The name of the agent to create
    overwrite
        Overwrite the agent file if it already exists
    template
        The template to use to create the agent file
    editor
        The editor to use to open the agent file
    no_edit
        Do not open the agent file in your editor
    """
    await telemetry.send_event(
        {
            "command": "agent create",
            "agent_name_sha256": hash_value(agent_name),
            **prepare_profile_for_telemetry(manager.get_active_profile()),
            "overwrite": overwrite,
            "template": template,
            "editor": editor,
            "no_edit": no_edit,
        }
    )
    agent_file = await create_agent(
        agent_name=agent_name,
        overwrite=overwrite,
        template=template,
    )
    # Open the file in the user's editor
    if editor and not no_edit:
        try:
            await edit_file(agent_file, editor)
        except ValueError:
            print(
                "[red]No editor specified. Set the $EDITOR environment variable or use --editor option.[/red]"
            )
            print(f"[blue]Please manually open {str(agent_file)!r} in your editor.[/blue]")
            sys.exit(1)
