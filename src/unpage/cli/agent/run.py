import sys
from typing import TYPE_CHECKING, cast

from rich import print

from unpage.agent.analysis import AnalysisAgent
from unpage.agent.utils import load_agent
from unpage.cli.agent._app import agent_app
from unpage.config import manager
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
    debug: bool = False,
    use_test_payload: str | None = None,
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
    debug
        Enable debug mode to print the history of the agent
    use_test_payload
        Use a predefined test payload defined in your agent yaml file (e.g. "pagerduty_incident" or "build_failure")
    """
    await telemetry.send_event(
        {
            "command": "agent run",
            **prepare_profile_for_telemetry(manager.get_active_profile()),
            "agent_name_sha256": hash_value(agent_name),
            "debug": debug,
            "has_payload": payload is not None,
            "has_pagerduty_incident": bool(pagerduty_incident),
        }
    )
    plugin_manager = PluginManager(manager.get_active_profile_config())
    data = ""
    if (pagerduty_incident and use_test_payload) and (
        payload is not None or not sys.stdin.isatty()
    ):
        print(
            "[red]Cannot pass --pagerduty-incident or --use-test-payload with --payload or stdin.[/red]"
        )
        sys.exit(1)

    if pagerduty_incident:
        incident_id = pagerduty_incident
        if "/" in pagerduty_incident:
            incident_id = [x for x in pagerduty_incident.split("/") if x][-1]
        pd = cast("PagerDutyPlugin", plugin_manager.get_plugin("pagerduty"))
        incident = await pd.get_incident_by_id(incident_id)
        data = incident.model_dump_json()

    if use_test_payload:
        agent = load_agent(agent_name)
        if not agent.test_payloads or use_test_payload not in agent.test_payloads:
            print(
                f"[red]Test payload {use_test_payload!r} not found in agent {agent_name!r}.[/red]"
            )
            if agent.test_payloads:
                print(
                    f"[bold]Available test payloads: {', '.join(agent.test_payloads.keys())}[/bold]"
                )
            sys.exit(1)
        data = agent.test_payloads[use_test_payload]

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
        agent = load_agent(agent_name)
    except FileNotFoundError as ex:
        print(f"[red]Agent {agent_name!r} not found at {str(ex.filename)!r}[/red]")
        print(f"[bold]Use 'unpage agent create {agent_name!r}' to create a new agent.[/bold]")
        sys.exit(1)

    # Run the analysis with the specific agent
    analysis_agent = AnalysisAgent()
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
