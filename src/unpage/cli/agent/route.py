import sys

from rich import print

from unpage.agent.analysis import AnalysisAgent
from unpage.cli.agent._app import agent_app
from unpage.config import manager
from unpage.telemetry import client as telemetry
from unpage.telemetry import prepare_profile_for_telemetry


@agent_app.command
async def route(
    payload: str | None = None,
    /,
    *,
    debug: bool = False,
) -> None:
    """Determine which agent will be used to analyze the given payload.

    A payload can be passed as an argument or piped to stdin.

    Parameters
    ----------
    payload
        The alert payload to analyze. Alternatively, you can pipe the payload to stdin.
    debug
        Enable debug mode to print the history of the routing agent.
    """
    await telemetry.send_event(
        {
            "command": "agent route",
            **prepare_profile_for_telemetry(manager.get_active_profile()),
            "debug": debug,
        }
    )
    # Read data from stdin if it's being piped to us.
    if not sys.stdin.isatty():
        if payload is not None:
            print("[red]Cannot pass a payload argument when piping data to stdin.[/red]")
            sys.exit(1)
        data = sys.stdin.read().strip()
    else:
        # Otherwise, use the payload argument.
        data = payload

    if not data:
        print("[red]No payload provided.[/red]")
        print(
            "[bold]Pass an alert payload as an argument or pipe the payload data to stdin.[/bold]"
        )
        sys.exit(1)

    # Run the analysis with the specific agent
    try:
        analysis_agent = AnalysisAgent()
        result = await analysis_agent.acall(payload=data, route_only=True)
        if debug:
            print("\n\n===== DEBUG OUTPUT =====\n")
            analysis_agent.inspect_history(n=1000)
            print("\n===== END DEBUG OUTPUT =====\n\n")
        print(result)
    except Exception as ex:
        print(f"[red]Analysis failed:[/red] {ex}")
        sys.exit(1)
