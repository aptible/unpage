import typer

from unpage.cli.mcp.client.logs.app import client_logs_app

client_app = typer.Typer(
    help="Debugging tools for clients of the Unpage MCP Server", no_args_is_help=True
)
client_app.add_typer(client_logs_app, name="logs")
