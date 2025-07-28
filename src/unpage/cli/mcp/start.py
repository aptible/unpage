import sys
import warnings

import anyio
import typer
from fastmcp import settings as fastmcp_settings

from unpage import mcp
from unpage.cli.mcp._app import mcp_app
from unpage.cli.options import PROFILE_OPTION
from unpage.telemetry import client as telemetry


@mcp_app.command()
def start(
    profile: str = PROFILE_OPTION,
    disable_sse: bool = typer.Option(
        False,
        "--disable-sse",
        help="Disable the HTTP transport for the MCP Server (deprecated, use --disable-http instead)",
    ),
    disable_stdio: bool = typer.Option(
        False, "--disable-stdio", help="Disable the stdio transport for the MCP Server"
    ),
    disable_http: bool = typer.Option(
        False, "--disable-http", help="Disable the HTTP transport for the MCP Server"
    ),
    http_host: str = typer.Option(
        fastmcp_settings.host, "--http-host", help="The host to bind the HTTP transport to"
    ),
    http_port: int = typer.Option(
        fastmcp_settings.port, "--http-port", help="The port to bind the HTTP transport to"
    ),
) -> None:
    """Start the Unpage MCP Server"""
    # Deprecate --disable-sse in favor of --disable-http
    if "--disable-sse" in sys.argv:
        disable_http = disable_sse
        warnings.warn(
            "The `--disable-sse` argument is deprecated. Use `--disable-http` instead.",
            DeprecationWarning,
            stacklevel=2,
        )

    async def _start() -> None:
        await telemetry.send_event(
            {
                "command": "start",
                "profile": profile,
                "disable_sse": disable_sse,
                "disable_stdio": disable_stdio,
                "disable_http": disable_http,
                "http_host": http_host,
                "http_port": http_port,
            }
        )
        await mcp.start(
            profile=profile,
            disable_stdio=disable_stdio,
            disable_http=disable_http,
            http_host=http_host,
            http_port=http_port,
        )

    anyio.run(_start)
