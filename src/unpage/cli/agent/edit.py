import sys

from rich import print

from unpage.agent.utils import get_agent_template
from unpage.cli.agent._app import agent_app
from unpage.config import manager
from unpage.telemetry import CommandEvents, hash_value
from unpage.utils import edit_file


@agent_app.command
async def edit(
    agent_name: str,
    /,
    *,
    editor: str | None = None,
) -> None:
    """Edit an existing agent configuration file.

    Parameters
    ----------
    agent_name
        The name of the agent to edit
    editor
        The editor to use to open the agent file; DAYDREAM_EDITOR and EDITOR environment variables also work
    """
    events = CommandEvents(
        "agent edit",
        {
            "agent_name_sha256": hash_value(agent_name),
            "editor": editor,
        },
    )
    await events.send("start")

    # Get the config directory for the profile
    config_dir = manager.get_active_profile_directory()

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
        await events.send("done", {"status": "failed - agent not found"})
        sys.exit(1)

    # Open the file in the user's editor
    orig_hash = hash_value(agent_file.read_text())
    try:
        await edit_file(agent_file, editor)
    except ValueError:
        print(
            "[red]No editor specified. Set the $EDITOR environment variable or use --editor option.[/red]"
        )
        print(f"[blue]Please manually open {str(agent_file)!r} in your editor.[/blue]")
        await events.send("done", {"status": "failed - could not open file"})
        sys.exit(1)
    await events.send(
        "done", {"status": "success", "changed": hash_value(agent_file.read_text()) != orig_hash}
    )
