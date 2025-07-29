import anyio
import rich

from unpage.cli.mcp.client.logs.app import client_logs_app
from unpage.telemetry import client as telemetry


@client_logs_app.command()
def claude() -> None:
    """Show logs for Claude Desktop Unpage MCP Server"""

    async def _run() -> None:
        rich.print("Logs are available at:")
        rich.print("~/Library/Logs/Claude/mcp.log")
        rich.print("~/Library/Logs/Claude/mcp-server-unpage.log")
        await telemetry.send_event(
            {
                "command": "mcp client logs claude",
            }
        )

    anyio.run(_run)
