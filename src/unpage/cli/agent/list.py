from typing import Annotated

import anyio
from rich import print

from unpage.agent.utils import get_agents
from unpage.cli.agent._app import agent_app
from unpage.cli.options import DEFAULT_PROFILE, ProfileParameter
from unpage.telemetry import client as telemetry
from unpage.telemetry import prepare_profile_for_telemetry


@agent_app.command
def list(*, profile: Annotated[str, ProfileParameter] = DEFAULT_PROFILE) -> None:
    """List the available agents."""

    async def _run() -> None:
        await telemetry.send_event(
            {
                "command": "agent list",
                **prepare_profile_for_telemetry(profile),
            }
        )
        print("Available agents:")
        for agent in sorted(get_agents(profile)):
            print(f"* {agent}")

    anyio.run(_run)
