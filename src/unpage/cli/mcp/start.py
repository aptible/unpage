import sys
import warnings

from fastmcp import settings as fastmcp_settings

from unpage import mcp
from unpage.cli.mcp._app import mcp_app
from unpage.config import manager
from unpage.telemetry import client as telemetry
from unpage.telemetry import prepare_profile_for_telemetry


@mcp_app.command
async def start(
    *,
    disable_sse: bool = False,
    disable_stdio: bool = False,
    disable_http: bool = False,
    http_host: str = fastmcp_settings.host,
    http_port: int = fastmcp_settings.port,
) -> None:
    """Start the Unpage MCP Server

    Parameters
    ----------
    disable_sse
        Disable the HTTP transport for the MCP Server (deprecated, use --disable-http instead)
    disable_stdio
        Disable the stdio transport for the MCP Server
    disable_http
        Disable the HTTP transport for the MCP Server
    http_host
        The host to bind the HTTP transport to
    http_port
        The port to bind the HTTP transport to
    """
    # Deprecate --disable-sse in favor of --disable-http
    if "--disable-sse" in sys.argv:
        disable_http = disable_sse
        warnings.warn(
            "The `--disable-sse` argument is deprecated. Use `--disable-http` instead.",
            DeprecationWarning,
            stacklevel=2,
        )

    await telemetry.send_event(
        {
            "command": "mcp start",
            **prepare_profile_for_telemetry(manager.get_active_profile()),
            "disable_sse": disable_sse,
            "disable_stdio": disable_stdio,
            "disable_http": disable_http,
            "http_host": http_host,
            "http_port": http_port,
        }
    )
    await mcp.start(
        disable_stdio=disable_stdio,
        disable_http=disable_http,
        http_host=http_host,
        http_port=http_port,
    )
