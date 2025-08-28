import os
from pathlib import Path

from pydantic_yaml import parse_yaml_file_as, parse_yaml_raw_as

from unpage.agent.analysis import Agent
from unpage.config import manager
from unpage.warnings import filter_all_warnings

TEMPLATE_DIR = Path(__file__).parent / "templates"


filter_all_warnings()


if os.environ.get("MLFLOW_TRACKING_URI"):
    import logging

    import mlflow

    mlflow_logger = logging.getLogger("mlflow")
    mlflow_logger.setLevel(logging.WARNING)
    print("> unpage: Found MLFLOW_TRACKING_URI environment variable, running `mlflow.autolog()`")
    mlflow.autolog()
    mlflow.set_experiment("Unpage Agent")


def get_agent_templates() -> list[str]:
    """Get the contents of the agent template for the given agent name."""
    return [
        str(template_file.relative_to(TEMPLATE_DIR).with_suffix(""))
        for template_file in TEMPLATE_DIR.glob("**/*.yaml")
    ]


def get_agent_template(agent_name: str) -> str:
    """Get the contents of the agent template for the given agent name."""
    return (Path(__file__).parent / "templates" / f"{agent_name}.yaml").read_text()


def get_agent_template_description(agent_name: str) -> str:
    text = get_agent_template(agent_name)
    yml = parse_yaml_raw_as(Agent, text)
    return yml.description


def get_agents() -> list[str]:
    """Get the names of the agents in the active profile's config directory."""
    agents_dir = manager.get_active_profile_directory() / "agents"
    agents = [
        str(agent_file.relative_to(agents_dir).with_suffix(""))
        for agent_file in agents_dir.glob("**/*.yaml")
    ]
    # Always include default agent
    if "default" not in agents:
        agents.append("default")
    return agents


def load_agent(agent_name: str) -> Agent:
    """Load the agent with the given name from the active profile."""
    agent_file = manager.get_active_profile_directory() / "agents" / f"{agent_name}.yaml"

    # If they're trying to load the default agent and it doesn't exist, create it.
    if not agent_file.exists() and agent_name == "default":
        agent_file.parent.mkdir(parents=True, exist_ok=True)
        agent_file.touch()
        agent_file.write_text(get_agent_template(agent_name))

    agent = parse_yaml_file_as(Agent, agent_file)
    if not agent.name:
        agent.name = agent_file.stem
    return agent


def delete_agent(agent_name: str) -> None:
    """Delete the agent with the given name from the active profile."""
    agent_file = manager.get_active_profile_directory() / "agents" / f"{agent_name}.yaml"
    agent_file.unlink()
