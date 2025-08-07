from cyclopts import App

from unpage.cli.mcp.client.logs.app import client_logs_app

client_app = App(help="Debugging tools for clients of the Unpage MCP Server")
client_app.command(client_logs_app, name="logs")
