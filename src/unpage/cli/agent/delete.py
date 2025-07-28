import hashlib

import anyio

from unpage.agent.utils import delete_agent
from unpage.cli.agent._app import agent_app
from unpage.cli.options import PROFILE_OPTION
from unpage.telemetry import client as telemetry


@agent_app.command()
def delete(agent_name: str, profile: str = PROFILE_OPTION) -> None:
    """Delete an agent."""

    async def _run() -> None:
        agent_hash = hashlib.sha256()
        agent_hash.update(agent_name.encode("utf-8"))
        await telemetry.send_event(
            {
                "command": "agent delete",
                "agent_name_sha256": agent_hash.hexdigest,
                "profile": profile,
            }
        )
        delete_agent(agent_name, profile)

    anyio.run(_run)
