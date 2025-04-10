import anyio
from rich import print

from unpage.agent.utils import get_agents
from unpage.cli.agent._app import agent_app
from unpage.cli.options import PROFILE_OPTION


@agent_app.command()
def list(profile: str = PROFILE_OPTION) -> None:
    """List the available agents."""

    async def _run() -> None:
        print("Available agents:")
        for agent in sorted(get_agents(profile)):
            print(f"* {agent}")

    anyio.run(_run)
