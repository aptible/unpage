import sys
from typing import TYPE_CHECKING, cast

import anyio
import typer
from rich import print

from unpage.agent.analysis import AnalysisAgent
from unpage.agent.utils import load_agent
from unpage.cli.agent._app import agent_app
from unpage.cli.options import PROFILE_OPTION
from unpage.config.utils import load_config
from unpage.plugins.base import PluginManager

if TYPE_CHECKING:
    from unpage.plugins.pagerduty.plugin import PagerDutyPlugin


@agent_app.command(
    help="Run an agent with the provided payload and print the analysis. A payload can be passed as an argument or piped to stdin."
)
def run(
    agent_name: str = typer.Argument(..., help="The name of the agent to run"),
    payload: str | None = typer.Argument(
        None,
        help="The alert payload to analyze. Alternatively, you can pipe the payload to stdin.",
    ),
    pagerduty_incident: str | None = typer.Option(
        None, help="PagerDuty incident ID or URL to use instead of payload or stdin"
    ),
    profile: str = PROFILE_OPTION,
    debug: bool = typer.Option(
        False,
        help="Enable debug mode to print the history of the agent.",
    ),
) -> None:
    """Run an agent with the provided payload and print the analysis."""

    async def _run() -> None:
        plugin_manager = PluginManager(load_config(profile, create=False))
        data = ""
        if pagerduty_incident:
            if payload is not None or not sys.stdin.isatty():
                print("[red]Cannot pass --pagerduty-incident with --payload or stdin.[/red]")
                raise typer.Exit(code=1)
            incident_id = pagerduty_incident
            if "/" in pagerduty_incident:
                incident_id = [x for x in pagerduty_incident.split("/") if x][-1]
            pd = cast("PagerDutyPlugin", plugin_manager.get_plugin("pagerduty"))
            incident = await pd.get_incident_by_id(incident_id)
            data = incident.model_dump_json()

        # Read data from stdin if it's being piped to us.
        if not data and not sys.stdin.isatty():
            if payload is not None:
                print("[red]Cannot pass a payload argument when piping data to stdin.[/red]")
                raise typer.Exit(code=1)
            data = sys.stdin.read().strip()
        elif not data:
            # Otherwise, use the payload argument.
            data = payload

        if not data:
            print("[red]No payload provided.[/red]")
            print(
                "[bold]Pass an alert payload as an argument or pipe the payload data to stdin.[/bold]"
            )
            raise typer.Exit(code=1)

        # Get the config directory and load the specific agent
        try:
            agent = load_agent(agent_name, profile)
        except FileNotFoundError as ex:
            print(f"[red]Agent {agent_name!r} not found at {str(ex.filename)!r}[/red]")
            print(f"[bold]Use 'unpage agent create {agent_name!r}' to create a new agent.[/bold]")
            raise typer.Exit(code=1) from ex

        # Run the analysis with the specific agent
        analysis_agent = AnalysisAgent(profile)
        try:
            result = await analysis_agent.acall(payload=data, agent=agent)
            print(result)
        except Exception as ex:
            print(f"[red]Analysis failed:[/red] {ex}")
            raise typer.Exit(code=1) from ex
        finally:
            if debug:
                print("\n\n===== DEBUG OUTPUT =====\n")
                analysis_agent.inspect_history(n=1000)
                print("\n===== END DEBUG OUTPUT =====\n\n")

    anyio.run(_run)
