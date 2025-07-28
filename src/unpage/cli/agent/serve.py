import os

import anyio
import typer

from unpage.agent.app import listen, settings
from unpage.cli.agent._app import agent_app
from unpage.telemetry import client as telemetry


@agent_app.command()
def serve(
    host: str = typer.Option(settings.UNPAGE_HOST, help="The host to bind to"),
    port: int = typer.Option(settings.UNPAGE_PORT, help="The port to bind to"),
    workers: int = typer.Option(settings.UNPAGE_WORKERS, help="The number of workers to use"),
    profile: str = typer.Option(settings.UNPAGE_PROFILE, help="The profile to use"),
    reload: bool = typer.Option(
        settings.UNPAGE_RELOAD, help="Reload the server when the code changes"
    ),
    tunnel: bool = typer.Option(settings.UNPAGE_TUNNEL, help="Tunnel the server through ngrok"),
    ngrok_token: str = typer.Option(
        os.getenv("NGROK_TOKEN"),
        help="The ngrok token to use to tunnel the server",
        show_default=False,
    ),
    ngrok_domain: str = typer.Option(
        settings.NGROK_DOMAIN, help="The ngrok domain to use to tunnel the server"
    ),
) -> None:
    """Run the Unpage Agent server, which loads all agents and routes between them. This is intended to be a webhook receiver for PagerDuty."""

    async def _serve() -> None:
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
                "profile": profile,
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

    anyio.run(_serve)
