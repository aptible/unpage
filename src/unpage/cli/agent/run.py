import sys
from typing import TYPE_CHECKING, Annotated, cast

from rich import print

from unpage.agent.analysis import AnalysisAgent
from unpage.agent.utils import load_agent
from unpage.cli.agent._app import agent_app
from unpage.cli.options import DEFAULT_PROFILE, ProfileParameter
from unpage.config.manager import manager
from unpage.plugins.base import PluginManager
from unpage.telemetry import client as telemetry
from unpage.telemetry import hash_value, prepare_profile_for_telemetry

if TYPE_CHECKING:
    from unpage.plugins.pagerduty.plugin import PagerDutyPlugin


@agent_app.command
async def run(
    agent_name: str,
    payload: str | None = None,
    /,
    *,
    pagerduty_incident: str | None = None,
    profile: Annotated[str, ProfileParameter] = DEFAULT_PROFILE,
    debug: bool = False,
) -> None:
    """Run an agent with the provided payload and print the analysis.

    A payload can be passed as an argument or piped to stdin.

    Parameters
    ----------
    agent_name
        The name of the agent to run
    payload
        The alert payload to analyze. Alternatively, you can pipe the payload to stdin.
    pagerduty_incident
        PagerDuty incident ID or URL to use instead of payload or stdin
    profile
        The profile to use
    debug
        Enable debug mode to print the history of the agent
    """
    await telemetry.send_event(
        {
            "command": "agent run",
            **prepare_profile_for_telemetry(profile),
            "agent_name_sha256": hash_value(agent_name),
            "debug": debug,
            "has_payload": payload is not None,
            "has_pagerduty_incident": bool(pagerduty_incident),
        }
    )
    plugin_manager = PluginManager(manager.get_profile_config(profile))
    data = ""
    if pagerduty_incident:
        if payload is not None or not sys.stdin.isatty():
            print("[red]Cannot pass --pagerduty-incident with --payload or stdin.[/red]")
            sys.exit(1)
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
            sys.exit(1)
        data = sys.stdin.read().strip()
    elif not data:
        # Otherwise, use the payload argument.
        data = payload

    if not data:
        print("[red]No payload provided.[/red]")
        print(
            "[bold]Pass an alert payload as an argument or pipe the payload data to stdin.[/bold]"
        )
        sys.exit(1)

    # Get the config directory and load the specific agent
    try:
        agent = load_agent(agent_name, profile)
    except FileNotFoundError as ex:
        print(f"[red]Agent {agent_name!r} not found at {str(ex.filename)!r}[/red]")
        print(f"[bold]Use 'unpage agent create {agent_name!r}' to create a new agent.[/bold]")
        sys.exit(1)

    # Run the analysis with the specific agent
    analysis_agent = AnalysisAgent(profile)
    try:
        result = await analysis_agent.acall(payload=data, agent=agent)
        print(result)
    except Exception as ex:
        print(f"[red]Analysis failed:[/red] {ex}")
        sys.exit(1)
    finally:
        if debug:
            print("\n\n===== DEBUG OUTPUT =====\n")
            analysis_agent.inspect_history(n=1000)
            print("\n===== END DEBUG OUTPUT =====\n\n")
