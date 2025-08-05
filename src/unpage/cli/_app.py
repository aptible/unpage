from cyclopts import App, Parameter

from unpage.cli.agent._app import agent_app
from unpage.cli.graph._app import graph_app
from unpage.cli.mcp._app import mcp_app
from unpage.cli.mlflow._app import mlflow_app
from unpage.warnings import filter_all_warnings

filter_all_warnings()

app = App(
    default_parameter=Parameter(
        # Disable automatic creation of "negative" options (e.g. --no-foo)
        negative=()
    )
)

app.command(agent_app, name="agent")
app.command(graph_app, name="graph")
app.command(mcp_app, name="mcp")
app.command(mlflow_app, name="mlflow")
