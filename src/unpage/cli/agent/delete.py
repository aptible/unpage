from typing import Annotated

import anyio

from unpage.agent.utils import delete_agent
from unpage.cli.agent._app import agent_app
from unpage.cli.options import DEFAULT_PROFILE, ProfileParameter
from unpage.telemetry import client as telemetry
from unpage.telemetry import hash_value, prepare_profile_for_telemetry


@agent_app.command
def delete(
    agent_name: str, /, *, profile: Annotated[str, ProfileParameter] = DEFAULT_PROFILE
) -> None:
    """Delete an agent.

    Parameters
    ----------
    agent_name
        The name of the agent to delete
    profile
        The profile to use
    """

    async def _run() -> None:
        await telemetry.send_event(
            {
                "command": "agent delete",
                "agent_name_sha256": hash_value(agent_name),
                **prepare_profile_for_telemetry(profile),
            }
        )
        delete_agent(agent_name, profile)

    anyio.run(_run)
