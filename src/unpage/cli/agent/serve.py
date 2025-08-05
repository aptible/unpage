import os

from unpage.agent.app import listen, settings
from unpage.cli.agent._app import agent_app
from unpage.telemetry import client as telemetry
from unpage.telemetry import prepare_profile_for_telemetry


@agent_app.command
async def serve(
    *,
    host: str = settings.UNPAGE_HOST,
    port: int = settings.UNPAGE_PORT,
    workers: int = settings.UNPAGE_WORKERS,
    profile: str = settings.UNPAGE_PROFILE,
    reload: bool = settings.UNPAGE_RELOAD,
    tunnel: bool = settings.UNPAGE_TUNNEL,
    ngrok_token: str = settings.NGROK_TOKEN,
    ngrok_domain: str = settings.NGROK_DOMAIN,
) -> None:
    """Run the Unpage Agent server, which loads all agents and routes between them. This is intended to be a webhook receiver for PagerDuty.

    Parameters
    ----------
    host
        The host to bind to
    port
        The port to bind to
    workers
        The number of workers to use
    profile
        The profile to use
    reload
        Reload the server when the code changes
    tunnel
        Tunnel the server through ngrok
    ngrok_token
        The ngrok token to use to tunnel the server
    ngrok_domain
        The ngrok domain to use to tunnel the server
    """
    await telemetry.send_event(
        {
            "command": "agent serve",
            "host": host
            if host.startswith("127")
            else "0.0.0.0"  # noqa: S104 Possible binding to all interfaces
            if host == "0.0.0.0"  # noqa: S104 Possible binding to all interfaces
            else f"{host.split('.')[0]}.0.0.0",
            "port": port,
            "workers": workers,
            **prepare_profile_for_telemetry(profile),
            "reload": reload,
            "tunnel": tunnel,
        }
    )
    await listen(
        host=host,
        port=port,
        workers=workers,
        profile=profile,
        tunnel=tunnel,
        ngrok_token=ngrok_token,
        ngrok_domain=ngrok_domain,
        reload=reload,
    )
