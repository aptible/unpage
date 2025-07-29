import typer

from unpage.cli.mcp.client._app import client_app
from unpage.cli.mcp.tools._app import tools_app

mcp_app = typer.Typer(help="MCP tool commands", no_args_is_help=True)
mcp_app.add_typer(tools_app, name="tools")
mcp_app.add_typer(client_app, name="client")
