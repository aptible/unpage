from pathlib import Path

import typer

from unpage.agent.utils import get_agent_template
from unpage.config.utils import get_config_dir


def create_agent(agent_name: str, profile: str, overwrite: bool, template: str) -> Path:
    # Create the default YAML content
    try:
        agent_template = get_agent_template(template)
    except FileNotFoundError as ex:
        print(
            f"Template '{template}' not found at {Path(__file__).parent / 'templates' / f'{template}.yaml'}"
        )
        raise typer.Abort() from ex

    # Get the config directory for the profile
    config_dir = get_config_dir(profile, create=True)

    # Create the agents directory if it doesn't exist
    agents_dir = config_dir / "agents"
    agents_dir.mkdir(exist_ok=True)

    # Create the agent file path
    agent_file = agents_dir / f"{agent_name}.yaml"

    # Check if the agent file already exists
    if agent_file.exists():
        if overwrite:
            print(f"Overwriting agent '{agent_name}' at {agent_file}")
        else:
            print(f"Agent '{agent_name}' already exists at {agent_file}")
            if not typer.confirm("Do you want to overwrite it?"):
                raise typer.Abort()

    # Write the YAML content to the file
    agent_file.write_text(agent_template, encoding="utf-8")

    print(f"Created agent configuration at {agent_file}")
    return agent_file
