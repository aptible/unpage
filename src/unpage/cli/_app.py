from typing import Annotated

import rich
from cyclopts import App, Group, Parameter

from unpage.cli.agent._app import agent_app
from unpage.cli.graph._app import graph_app
from unpage.cli.mcp._app import mcp_app
from unpage.cli.mlflow._app import mlflow_app
from unpage.cli.profile._app import profile_app
from unpage.config import manager
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
app.command(profile_app, name="profile")


@app.meta.default
def _app_launcher(
    *tokens: Annotated[str, Parameter(show=False, allow_leading_hyphen=True)],
    profile: str = manager.get_active_profile(),
) -> None:
    # Let the user know when they're overriding the active profile.
    if profile != manager.get_active_profile():
        rich.print(f"[blue]Active profile: {profile}[/blue]")

    with manager.active_profile(profile):
        app(tokens)


# Rename the meta's "Parameter" -> "Session Parameters".
# Set sort_key so it will be drawn higher up the help-page.
app.meta.group_parameters = Group("Session Parameters", sort_key=0)
