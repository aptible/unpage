import sys
from pathlib import Path

from unpage.agent.utils import get_agent_template
from unpage.config import manager
from unpage.utils import confirm


async def create_agent(agent_name: str, overwrite: bool, template: str) -> Path:
    # Create the default YAML content
    try:
        agent_template = get_agent_template(template)
    except FileNotFoundError:
        print(
            f"Template '{template}' not found at {Path(__file__).parent / 'templates' / f'{template}.yaml'}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Get the config directory for the active profile
    config_dir = manager.get_active_profile_directory()

    # Create the agents directory if it doesn't exist
    agents_dir = config_dir / "agents"
    agents_dir.mkdir(exist_ok=True, parents=True)

    # Create the agent file path
    agent_file = agents_dir / f"{agent_name}.yaml"

    # Check if the agent file already exists
    if agent_file.exists():
        if overwrite:
            print(f"Overwriting agent '{agent_name}' at {agent_file}")
        else:
            print(f"Agent '{agent_name}' already exists at {agent_file}")
            if not await confirm("Do you want to overwrite it?"):
                sys.exit(1)

    # Write the YAML content to the file
    agent_file.write_text(agent_template, encoding="utf-8")

    print(f"Created agent configuration at {agent_file}")
    return agent_file
