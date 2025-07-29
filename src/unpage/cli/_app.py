import typer

from unpage.cli.agent._app import agent_app
from unpage.cli.graph._app import graph_app
from unpage.cli.mcp._app import mcp_app
from unpage.cli.mlflow._app import mlflow_app

app = typer.Typer(context_settings={"help_option_names": ["-h", "--help"]}, no_args_is_help=True)
app.add_typer(mcp_app, name="mcp")
app.add_typer(graph_app, name="graph")
app.add_typer(agent_app, name="agent")
app.add_typer(mlflow_app, name="mlflow")
