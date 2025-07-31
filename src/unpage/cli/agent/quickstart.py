import asyncio
import os
import sys
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, cast

import anyio
import human_readable
import questionary
import rich
import typer
from pydantic import BaseModel
from questionary import Choice
from rich.console import Console
from rich.panel import Panel

from unpage.agent.analysis import AnalysisAgent
from unpage.agent.utils import load_agent
from unpage.cli.agent._app import agent_app
from unpage.cli.agent.create import create_agent
from unpage.cli.configure import welcome_to_unpage
from unpage.cli.options import DEFAULT_PROFILE, PROFILE_OPTION
from unpage.config.utils import Config, PluginConfig, load_config, save_config
from unpage.plugins.base import PluginManager
from unpage.plugins.datadog.plugin import DatadogPlugin
from unpage.plugins.llm.plugin import LlmPlugin
from unpage.plugins.pagerduty.models import PagerDutyIncident
from unpage.plugins.pagerduty.plugin import PagerDutyPlugin
from unpage.plugins.papertrail.plugin import PapertrailPlugin
from unpage.telemetry import client as telemetry
from unpage.telemetry import hash_value, prepare_profile_for_telemetry
from unpage.utils import confirm, edit_file, select


async def _send_event(step: str, profile: str, extra_params: dict[Any, Any] | None = None) -> None:
    await telemetry.send_event(
        {
            "command": "agent quickstart",
            "step": step,
            **prepare_profile_for_telemetry(profile),
            **(extra_params if extra_params else {}),
        }
    )


@agent_app.command()
def quickstart(
    profile: str = PROFILE_OPTION,
) -> None:
    """Get up-and-running with an incident agent in less than 5 minutes!"""

    async def _quickstart() -> None:
        await _send_event("start", profile)
        welcome_to_unpage()
        _quickstart_intro()
        cfg, next_step_count = await _create_config(
            Config(plugins=_initial_plugin_settings(profile)), profile
        )
        plugin_manager = PluginManager(cfg)
        save_config(cfg, profile, create=True)
        await _send_event("config_saved", profile)
        agent_name = await _create_and_edit_agent(profile, next_step_count)
        await _send_event("agent_created", profile)
        await _demo_an_incident(profile, agent_name, next_step_count + 1, plugin_manager)
        await _send_event("incident_demoed", profile)
        await _show_agent_commands(next_step_count + 2)
        await _send_event("shown_agent_commands", profile)
        await _optionally_launch_configure(next_step_count + 3, profile)

    anyio.run(_quickstart)


def _quickstart_intro() -> None:
    rich.print("""This interactive tool will walk through the configuration of your system.
We'll setup basic plugins so your LLM can use the Unpage MCP server.


Here's what the quickstart will entail:

1. Configure LLM (Amazon Bedrock, OpenAI, Anthropic Claude, and many more!)
2. Configure Pagerduty plugin
3. Optionally configure Papertrail
4. Optionally configure Datadog
5. Create and edit a demo agent
6. Test the demo agent against a PagerDuty incident
7. See how to create, test and refine your own agents
8. Configure and build an infrastructure knowledge graph
""")


def _initial_plugin_settings(profile: str) -> dict[str, PluginConfig]:
    try:
        existing_config = load_config(profile, create=False)
    except Exception:
        existing_config = Config(plugins={})
    return {
        "core": PluginConfig(enabled=True),
        "networking": PluginConfig(enabled=True),
        "llm": PluginConfig(
            enabled=True,
            settings=(
                LlmPlugin.default_plugin_settings
                if "llm" not in existing_config.plugins
                else existing_config.plugins["llm"].settings
            ),
        ),
        "pagerduty": PluginConfig(
            enabled=True,
            settings=(
                PagerDutyPlugin.default_plugin_settings
                if "pagerduty" not in existing_config.plugins
                else existing_config.plugins["pagerduty"].settings
            ),
        ),
        "papertrail": PluginConfig(
            enabled=False,
            settings=(
                PapertrailPlugin.default_plugin_settings
                if "papertrail" not in existing_config.plugins
                else existing_config.plugins["papertrail"].settings
            ),
        ),
        "datadog": PluginConfig(
            enabled=False,
            settings=(
                DatadogPlugin.default_plugin_settings
                if "datadog" not in existing_config.plugins
                else existing_config.plugins["datadog"].settings
            ),
        ),
    }


async def _create_config(cfg: Config, profile: str) -> tuple[Config, int]:
    plugin_manager = PluginManager(cfg)
    required_plugins = [
        "llm",
        "pagerduty",
    ]
    for i, plugin in enumerate(required_plugins):
        console = Console()
        console.print(
            Panel(
                f"[bold]{i + 1}. {plugin.upper() if plugin == 'llm' else plugin.capitalize()} configuration[/bold]",
                width=80,
            )
        )
        attempts = 1
        while True:
            cfg.plugins[plugin].settings = await plugin_manager.get_plugin(
                plugin
            ).interactive_configure()
            plugin_manager = PluginManager(cfg)
            if await _plugin_valid(plugin_manager, plugin):
                await _send_event(
                    f"plugin_valid_{plugin}",
                    profile,
                    extra_params={
                        "attempts": attempts,
                    },
                )
                break
            rich.print(f"Validation failed for {plugin}")
            if not await confirm("Retry?"):
                await _send_event(
                    f"plugin_invalid_{plugin}",
                    profile,
                    extra_params={
                        "attempts": attempts,
                    },
                )
                break
            attempts += 1
            rich.print("")
        rich.print("")
    optional_plugins = [
        "papertrail",
        "datadog",
    ]
    for i, optional_plugin in enumerate(optional_plugins):
        console = Console()
        console.print(
            Panel(
                f"[bold]{i + len(required_plugins) + 1}. {optional_plugin.upper() if optional_plugin == 'llm' else optional_plugin.capitalize()} configuration (optional)[/bold]",
                width=80,
            )
        )
        if await confirm(
            f"Would you like to enable and configure {optional_plugin.upper() if optional_plugin == 'llm' else optional_plugin.capitalize()}",
            default=False,
        ):
            cfg.plugins[optional_plugin].enabled = True
            attempts = 1
            while True:
                cfg.plugins[optional_plugin].settings = await plugin_manager.get_plugin(
                    optional_plugin
                ).interactive_configure()
                plugin_manager = PluginManager(cfg)
                if await _plugin_valid(plugin_manager, optional_plugin):
                    await _send_event(
                        f"plugin_valid_{optional_plugin}",
                        profile,
                        extra_params={
                            "attempts": attempts,
                        },
                    )
                    break
                rich.print(f"Validation failed for {optional_plugin}")
                if not await confirm("Retry?"):
                    await _send_event(
                        f"plugin_invalid_{optional_plugin}",
                        profile,
                        extra_params={
                            "attempts": attempts,
                        },
                    )
                    break
                attempts += 1
        else:
            await _send_event(f"plugin_disabled_{optional_plugin}", profile)
        rich.print("")
    next_step_count = len(required_plugins) + len(optional_plugins) + 1
    return (cfg, next_step_count)


async def _plugin_valid(plugin_manager: PluginManager, plugin: str) -> bool:
    rich.print(f"Validating {plugin}...")
    try:
        await plugin_manager.get_plugin(plugin).validate_plugin_config()
    except Exception as ex:
        rich.print(f"Error validating {plugin}:\n{ex}")
        return False
    rich.print(f"[green]{plugin} configuration is valid![/green]")
    return True


async def _create_and_edit_agent(profile: str, next_step_count: int) -> str:
    console = Console()
    console.print(Panel(f"[bold]{next_step_count}. Create and edit demo agent[/bold]", width=80))
    agent_name = "demo-quickstart"
    template = "demo_quickstart"
    agent_file = create_agent(agent_name, profile, True, template)
    await _send_event(
        "created_agent",
        profile,
        {
            "agent_name_sha256": hash_value(agent_name),
            "template": template,
        },
    )
    rich.print("")
    rich.print(f"> We created a new agent called {agent_name}!")
    rich.print(
        "> When you're ready, we'll open the agent template in your editor so you can preview it and optionally make changes before testing."
    )
    rich.print("")
    await questionary.press_any_key_to_continue().unsafe_ask_async()
    await edit_file(agent_file)
    rich.print("")
    return agent_name


async def _enter_incident_id_or_url(pd: PagerDutyPlugin) -> PagerDutyIncident | None:
    while True:
        answer = await questionary.text(
            "PagerDuty incident ID or URL",
        ).unsafe_ask_async()
        incident_id = answer
        if "/" in answer:
            incident_id = [x for x in answer.split("/") if x][-1]
        try:
            return await pd.get_incident_by_id(incident_id)
        except Exception as ex:
            rich.print(f"Failed to retrieve incident with id {incident_id}: {ex}")
            if not await confirm("Retry with another id or url?"):
                return None


async def _select_incident_from_recent_100(pd: PagerDutyPlugin) -> PagerDutyIncident | None:
    incidents: list[PagerDutyIncident] = []
    console = Console()
    with console.status("querying incidents...", spinner="dots") as status:
        async for incident in pd.recent_incident_payloads():
            incidents.append(incident.incident)
            if len(incidents) >= 100:
                break
        status.update("Done 🎉")
    enable_search = len(incidents) > 10
    incident_id = await select(
        "Select a PagerDuty incident",
        choices=[
            Choice(
                f"{i.title} [{i.urgency}] [{i.id}]",
                value=i.id,
            )
            for i in incidents
        ],
        use_search_filter=enable_search,
        use_jk_keys=not enable_search,
    )
    for incident in incidents:
        if incident.id == incident_id:
            return incident


async def _random_incident_from_recent(pd: PagerDutyPlugin) -> PagerDutyIncident | None:
    async for incident in pd.recent_incident_payloads():
        return incident.incident


async def _select_pagerduty_incident(pd: PagerDutyPlugin, profile: str) -> PagerDutyIncident | None:
    class incidentChooser(BaseModel):
        title: str
        func: Callable[[PagerDutyPlugin], Awaitable[PagerDutyIncident | None]]

    opts = [
        incidentChooser(
            title="Enter an incident id or url",
            func=_enter_incident_id_or_url,
        ),
        incidentChooser(
            title="Select from the most recent 100 incidents",
            func=_select_incident_from_recent_100,
        ),
        incidentChooser(
            title="Have us select a recent incident",
            func=_random_incident_from_recent,
        ),
    ]
    while True:
        choice = await select(
            "How would you like to select a PagerDuty incident?",
            choices=[Choice(o.title, value=str(i)) for i, o in enumerate(opts)],
        )
        incident = await opts[int(choice)].func(pd)
        if incident:
            await _send_event(
                "selected_pagerduty_incident",
                profile,
                {"selection_method": opts[int(choice)].title},
            )
            return incident
        rich.print("Oops, did not get an incident id to test with")
        if not await confirm("Retry?"):
            return None


async def _demo_an_incident(
    profile: str, agent_name: str, next_step_count: int, plugin_manager: PluginManager
) -> None:
    console = Console()
    console.print(Panel(f"[bold]{next_step_count}. Demo time![/bold]", width=80))
    rich.print("")
    rich.print("Now we can test the agent output with one of your existing PagerDuty incidents!")
    rich.print("")
    pd = cast("PagerDutyPlugin", plugin_manager.get_plugin("pagerduty"))
    incident = await _select_pagerduty_incident(pd, profile)
    if not incident:
        rich.print("Did not get an incident, skipping the demo.")
        return
    try:
        agent = load_agent(agent_name, profile)
        analysis_agent = AnalysisAgent(profile)
        rich.print("")
        rich.print("Details of the incident we're going to demo:")
        rich.print(f"> Title: {incident.title}")
        time_since = datetime.now(UTC) - incident.created_at
        rich.print(
            f"> Created: {incident.created_at} ({human_readable.precise_delta(time_since)} ago)"
        )

        def _color(status: str) -> str:
            match status:
                case "triggered":
                    return f"[red]{incident.status}[/red]"
                case "acknowledged":
                    return f"[yellow]{incident.status}[/yellow]"
            return incident.status

        rich.print(f"> Status: {_color(incident.status)}")
        rich.print(f"> Urgency: {incident.urgency}")
        rich.print(f"> Url: {incident.html_url}")
        rich.print("")
        rich.print("> Ready to run the demo agent on this incident?")
        rich.print("")
        await questionary.press_any_key_to_continue().unsafe_ask_async()
        incident_json = incident.model_dump_json(indent=2)
        incident_json_lines = incident_json.splitlines()
        truncated = False
        if len(incident_json_lines) > 20:
            incident_json = "\n".join(incident_json_lines[-20:])
            truncated = True
        rich.print("")
        rich.print(f"> PagerDuty incident payload{' (last 20 lines)' if truncated else ''}:")
        if truncated:
            rich.print("...")
        rich.print(incident_json)
        rich.print("> Computing status update... (this may take a minute!)")
        console = Console()
        with console.status("working...", spinner="dots") as status:
            result = await analysis_agent.acall(payload=incident.model_dump_json(), agent=agent)
            status.update("Done 🎉")
        rich.print("")
        rich.print(
            f"> Status update that would be posted to PagerDuty by the {pd.default_from} user:\n"
        )
        rich.print("-----")
        rich.print(result)
        rich.print("-----")
        rich.print("")
        rich.print("You can re-run this demo at any point with:")
        rich.print("")
        rich.print(
            f"  [bold deep_sky_blue1]uvx unpage{f' --profile {profile}' if profile != DEFAULT_PROFILE else ''} agent run --pagerduty-incident {incident.id} demo-quickstart[/bold deep_sky_blue1]"
        )
        rich.print("")
    except Exception as ex:
        rich.print(f"[red] Demo failed:[/red] {ex}")
        raise typer.Exit(1) from ex
    rich.print("> Congrats on completing the demo agent! You did it! 🎉")
    rich.print("")
    rich.print("> Ready to move on?")
    rich.print("")
    await questionary.press_any_key_to_continue().unsafe_ask_async()
    rich.print("")


async def _show_agent_commands(next_step_count: int) -> None:
    console = Console()
    console.print(
        Panel(f"[bold]{next_step_count}. Create, test and refine your own agents[/bold]", width=80)
    )
    rich.print("")
    rich.print(
        "> You can create, edit, run, and serve agents using the [bold deep_sky_blue1]uvx unpage agent[/bold deep_sky_blue1] subcommands:"
    )
    rich.print("> ")
    agent_help_cmd = " ".join([a if a != "quickstart" else "--help" for a in sys.argv])
    rich.print("> $ [bold deep_sky_blue1]uvx unpage agent --help[/bold deep_sky_blue1]")
    rich.print("")
    await (await asyncio.subprocess.create_subprocess_shell(agent_help_cmd)).wait()
    rich.print("> ")
    rich.print("")
    rich.print(
        "> Next, you can build the knowledge graph of your infrastructure. This will give your agents more tools and context, so you get better results. Ready to learn more about the knowledge graph?"
    )
    rich.print("")
    await questionary.press_any_key_to_continue().unsafe_ask_async()
    rich.print("")


async def _optionally_launch_configure(next_step_count: int, profile: str) -> None:
    console = Console()
    console.print(
        Panel(f"[bold]{next_step_count}. Infrastructure Knowledge Graph[/bold]", width=80)
    )
    rich.print("")
    rich.print(
        "> Unpage supports a rich infrastructure knowledge graph builder, which can be used on its own or automatically "
        "integrated with your Unpage Agents. The graph can be built from your infrastructure tools, like AWS or Aptible, and your "
        "observability tools, like Datadog and Cloudwatch."
    )
    rich.print("")
    rich.print(
        "> Use the [bold deep_sky_blue1]uvx unpage configure[/bold deep_sky_blue1] command to configure all plugins required for graph building."
    )
    rich.print(
        "> Then use [bold deep_sky_blue1]uvx unpage graph build[/bold deep_sky_blue1] to build the infrastructure knowledge graph."
    )
    rich.print(">")
    rich.print(
        "> Your Unpage Agents will automatically begin using the knowledge graph once it is built."
    )
    rich.print(">")
    if not await confirm("Would you like to run uvx unpage configure now?"):
        await _send_event("done_no_configure", profile)
        return
    rich.print(">")
    await _send_event("starting_configure", profile)
    _replace_current_proc_with_unpage_configure()


def _replace_current_proc_with_unpage_configure() -> None:
    configure_cmd = [a if a != "agent" else "configure" for a in sys.argv if a != "quickstart"]
    rich.print("> Running: [bold deep_sky_blue1]uvx unpage configure[/bold deep_sky_blue1]")
    rich.print("")
    os.execvp(configure_cmd[0], configure_cmd)  # noqa: S606 Starting a process without a shell
