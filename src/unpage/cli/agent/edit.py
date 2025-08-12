import sys
from typing import Annotated

from rich import print

from unpage.agent.utils import get_agent_template
from unpage.cli.agent._app import agent_app
from unpage.cli.options import DEFAULT_PROFILE, ProfileParameter
from unpage.config.manager import manager
from unpage.telemetry import client as telemetry
from unpage.telemetry import hash_value, prepare_profile_for_telemetry
from unpage.utils import edit_file, get_editor


@agent_app.command
async def edit(
    agent_name: str,
    /,
    *,
    profile: Annotated[str, ProfileParameter] = DEFAULT_PROFILE,
    editor: str | None = get_editor(),
) -> None:
    """Edit an existing agent configuration file.

    Parameters
    ----------
    agent_name
        The name of the agent to edit
    profile
        The profile to use
    editor
        The editor to use to open the agent file; DAYDREAM_EDITOR and EDITOR environment variables also work
    """
    await telemetry.send_event(
        {
            "command": "agent edit",
            "agent_name_sha256": hash_value(agent_name),
            **prepare_profile_for_telemetry(profile),
            "editor": editor,
        }
    )
    # Get the config directory for the profile
    config_dir = manager.get_profile_directory(profile)

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
        sys.exit(1)

    # Open the file in the user's editor
    try:
        await edit_file(agent_file, editor)
    except ValueError:
        print(
            "[red]No editor specified. Set the $EDITOR environment variable or use --editor option.[/red]"
        )
        print(f"[blue]Please manually open {str(agent_file)!r} in your editor.[/blue]")
        sys.exit(1)
