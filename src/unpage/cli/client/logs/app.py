import typer

client_logs_app = typer.Typer(
    help="Show logs for a client of the Unpage MCP Server, like Claude Desktop",
    no_args_is_help=True,
)
