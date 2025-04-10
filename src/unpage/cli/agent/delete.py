import anyio

from unpage.agent.utils import delete_agent
from unpage.cli.agent._app import agent_app
from unpage.cli.options import PROFILE_OPTION


@agent_app.command()
def delete(agent_name: str, profile: str = PROFILE_OPTION) -> None:
    """Delete an agent."""

    async def _run() -> None:
        delete_agent(agent_name, profile)

    anyio.run(_run)
