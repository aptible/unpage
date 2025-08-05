from cyclopts import App

from unpage.cli.mcp.client._app import client_app
from unpage.cli.mcp.tools._app import tools_app

mcp_app = App(help="MCP tool commands")
mcp_app.command(tools_app, name="tools")
mcp_app.command(client_app, name="client")
