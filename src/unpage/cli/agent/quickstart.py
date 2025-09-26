import contextlib
import json
import sys
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, cast

import questionary
import rich
from pydantic import BaseModel
from questionary import Choice
from rich.console import Console
from rich.panel import Panel

from unpage.agent.analysis import Agent, AnalysisAgent
from unpage.agent.utils import (
    get_agent_file,
    get_agent_template_description,
    get_agent_templates,
    load_agent,
)
from unpage.cli.agent._app import agent_app
from unpage.cli.agent.create import create_agent
from unpage.cli.configure import welcome_to_unpage
from unpage.config import Config, PluginConfig, PluginSettings, manager
from unpage.plugins.base import REGISTRY, PluginManager
from unpage.plugins.pagerduty.plugin import PagerDutyPlugin
from unpage.plugins.rootly.plugin import RootlyPlugin
from unpage.telemetry import UNPAGE_TELEMETRY_DISABLED, CommandEvents, hash_value
from unpage.utils import confirm, edit_file, select

if TYPE_CHECKING:
    from unpage.plugins.pagerduty.models import PagerDutyIncident
    from unpage.plugins.rootly.models import RootlyIncident


def _panel(text: str) -> None:
    console = Console()
    console.print(Panel(f"[bold]{text}[/bold]", width=80))


@agent_app.command
async def quickstart() -> None:
    """Get up-and-running with an incident agent in less than 5 minutes!"""
    e = CommandEvents("agent quickstart")
    await e.send("start")
    welcome_to_unpage()
    if not await _quickstart_intro():
        await e.send("abandon", {"abandon_reason": "user_declined_intro"})
        return
    rich.print("")
    agent = await _select_template_and_create_agent(e)
    agent = await _edit_agent(agent, e)
    required_plugins, required_plugin_names_that_need_config = await _plugins_to_config_for_agent(
        agent, e
    )
    while not await confirm("Ready to configure these plugins? (No to edit the agent file again)"):
        agent = await _edit_agent(agent, e)
        (
            required_plugins,
            required_plugin_names_that_need_config,
        ) = await _plugins_to_config_for_agent(agent, e)
    rich.print("")
    rich.print("")
    cfg = await _configure_plugins(
        agent, required_plugins, required_plugin_names_that_need_config, e
    )
    plugin_manager = PluginManager(cfg)
    await _demo_an_incident(agent, plugin_manager, e)
    await e.send("complete")


async def _quickstart_intro() -> bool:
    rich.print("""
Unpage is the open source framework for building SRE agents with infrastructure context and secure access to any dev tool.

This quickstart flow will show you how easily you can build your own custom agents for automation. Here's what it will entail:

• Create your first agent. Choose from our pre-defined templates, or build your own from scratch!
• Configure the agent. Give it access to the tools & context it needs
• Run the agent with a test payload to assess the output
""")
    return await confirm("That's it! Ready to get started?")


async def _select_template_and_create_agent(e: CommandEvents) -> Agent:
    _panel("Create your first agent")
    rich.print(
        "First, which agent would you like to try? Choose a template, or make one from scratch. If it's your first time, we recommend starting with a template."
    )
    rich.print("")
    rich.print("----------")
    rich.print("")
    demo_template_names = [
        "default",
        *sorted(t for t in get_agent_templates() if t != "default" and t != "blank"),
    ]
    choices = [
        Choice(
            title=t,
            value=t,
            description=get_agent_template_description(t),
        )
        for t in demo_template_names
    ]
    choices.append(
        Choice(
            title="Build my own from scratch",
            value="blank",
            description="Build your own agent from scratch",
        )
    )
    template_selected = await select(
        "Select a demo agent:",
        choices=choices,
    )
    rich.print("")
    agent_name = f"demo_quickstart__{template_selected}"
    await create_agent(
        agent_name=agent_name,
        overwrite=True,
        template=template_selected,
    )
    await e.send(
        "agent created", {"template": template_selected, "agent_name_hash": hash_value(agent_name)}
    )
    rich.print("")
    rich.print(
        f"Great! You selected {template_selected if template_selected != 'blank' else 'to build your own template'}. When you're ready, we'll open the agent's configuration file in your default editor so you can (optionally) make changes. Make note of the tools that the agent has access to, as this will determine the plugins we'll need to setup before we can test the agent."
    )
    rich.print("")
    return load_agent(agent_name)


async def _edit_agent(agent: Agent, e: CommandEvents) -> Agent:
    _panel("Edit your agent")
    await questionary.press_any_key_to_continue("Hit [enter] to open the editor").unsafe_ask_async()
    agent_file = get_agent_file(agent.name)
    orig_hash = hash_value(agent_file.read_text())
    await edit_file(agent_file)
    await e.send(
        "agent edited",
        {
            "agent_name_hash": hash_value(agent.name),
            "agent_file_changed": hash_value(agent_file.read_text()) != orig_hash,
        },
    )
    rich.print("")
    rich.print(f"You successfully edited the {agent.name} agent! ✨")
    rich.print("")
    return load_agent(agent.name)


async def _interactive_plugin_config(
    plugin_name: str, existing_plugin_settings: PluginSettings | None
) -> PluginSettings:
    plugin_cls = REGISTRY[plugin_name]
    plugin = plugin_cls(
        **{
            **plugin_cls.default_plugin_settings,
            **(existing_plugin_settings if existing_plugin_settings else {}),
        }
    )
    return await plugin.interactive_configure()


async def _plugin_settings_valid(plugin_name: str, plugin_settings: PluginSettings) -> bool:
    plugin_cls = REGISTRY[plugin_name]
    plugin = plugin_cls(**plugin_settings)
    rich.print(f"Validating {plugin.name}...")
    try:
        await plugin.validate_plugin_config()
    except Exception as ex:
        rich.print(f"Error validating {plugin.name}:\n{ex}")
        return False
    rich.print(f"[green]{plugin.name} configuration is valid![/green]")
    return True


async def _plugins_to_config_for_agent(
    agent: Agent, e: CommandEvents
) -> tuple[list[str], list[str]]:
    _panel("Configure the agent")
    rich.print(
        "Before we test the agent, we need to configure some plugins. Based on the tools this agent has access to, it looks like we'll need API keys for the following:"
    )
    rich.print("")
    required_plugin_names = [
        "llm",
        *sorted(a for a in agent.required_plugins_from_tools() if a != "llm"),
    ]
    required_plugin_names_that_need_config = [
        plugin_name
        for plugin_name in required_plugin_names
        if "interactive_configure" in REGISTRY[plugin_name].__dict__
        and callable(REGISTRY[plugin_name].interactive_configure)
    ]
    await e.send(
        "plugins identified",
        {
            "required_plugins": required_plugin_names,
            "required_plugins_that_need_config": required_plugin_names_that_need_config,
        },
    )
    for plugin_name in required_plugin_names_that_need_config:
        rich.print(f"• {plugin_name.upper() if plugin_name == 'llm' else plugin_name.capitalize()}")
    rich.print("")
    rich.print(
        "Don't worry, the LLM won't see your API keys. They're only used in the configuration file to make the tool calls work."
    )
    rich.print("")
    rich.print(
        "Don't use one of these services? You can still use this agent! Learn more in our Getting Started guide at: https://docs.unpage.ai/?utm_source=unpage"
    )
    rich.print("")
    return required_plugin_names, required_plugin_names_that_need_config


async def _configure_plugins(
    agent: Agent,
    required_plugin_names: list[str],
    required_plugin_names_that_need_config: list[str],
    e: CommandEvents,
) -> Config:
    existing_plugins: dict[str, PluginConfig] = {}
    try:
        existing_config = manager.get_active_profile_config()
        existing_plugins = existing_config.plugins
    except Exception:  # noqa: S110 try-except-pass
        pass
    plugins = {}
    for i, plugin_name in enumerate(required_plugin_names_that_need_config):
        existing_plugin_settings = None
        if plugin_name in existing_plugins:
            existing_plugin_settings = existing_plugins[plugin_name].settings
        step_number = i + 1
        rich.print(
            f"[bold] {step_number}. {plugin_name.upper() if plugin_name == 'llm' else plugin_name.capitalize()} configuration[/bold]"
        )
        rich.print("-" * 80)
        attempts = 1
        plugin_config_validated = False
        while True:
            plugin_settings = await _interactive_plugin_config(
                plugin_name=plugin_name,
                existing_plugin_settings=existing_plugin_settings,
            )
            if plugin_config_validated := await _plugin_settings_valid(
                plugin_name, plugin_settings
            ):
                plugins[plugin_name] = PluginConfig(enabled=True, settings=plugin_settings)
                rich.print("")
                break
            rich.print(f"Validation failed for {plugin_name}")
            if not await confirm("Retry?"):
                rich.print(f"⏭️ Skipping configuration of {plugin_name}")
                break
            rich.print("")
            attempts += 1
        await e.send(
            f"plugin configured {plugin_name}",
            {"attempts": attempts, "plugin_config_validated": plugin_config_validated},
        )
        rich.print("")
    cfg = manager.get_empty_config(
        profile=manager.get_active_profile(),
        telemetry_enabled=not UNPAGE_TELEMETRY_DISABLED,
        plugins={
            **plugins,
            **{
                plugin_name: PluginConfig(
                    enabled=True,
                    settings=REGISTRY[plugin_name].default_plugin_settings,
                )
                for plugin_name in required_plugin_names
                if plugin_name not in required_plugin_names_that_need_config
            },
        },
    )
    rich.print("")
    return cfg


async def _provide_incident_id_or_url(pd: PagerDutyPlugin) -> str | None:
    """Prompt user to enter a PagerDuty incident ID or URL."""
    while True:
        answer = await questionary.text(
            "Enter PagerDuty incident ID or URL:",
        ).unsafe_ask_async()

        if not answer:
            return None

        incident_id = answer
        if "/" in answer:
            incident_id = [x for x in answer.split("/") if x][-1]

        try:
            incident = await pd.get_incident_by_id(incident_id)
            return incident.model_dump_json(indent=2)
        except Exception as ex:
            rich.print(f"[red]Failed to retrieve incident with id {incident_id}: {ex}[/red]")
            if not await confirm("Retry with another ID or URL?"):
                return None


async def _select_from_recent_incidents(
    pd: PagerDutyPlugin, incidents_to_consider: int = 20
) -> str | None:
    incidents: list[PagerDutyIncident] = []
    console = Console()

    with console.status("Fetching recent incidents...", spinner="dots") as status:
        async for incident in pd.recent_incident_payloads():
            incidents.append(incident.incident)
            if len(incidents) >= incidents_to_consider:
                break
        status.update("Done 🎉")

    if not incidents:
        rich.print("[yellow]No recent incidents found.[/yellow]")
        return None

    enable_search = len(incidents) > 10
    incident_id = await select(
        "Select an incident:",
        choices=[
            Choice(
                f"{i.title[:60]}... [{i.urgency}]"
                if len(i.title) > 60
                else f"{i.title} [{i.urgency}]",
                value=i.id,
            )
            for i in incidents
        ],
        use_search_filter=enable_search,
        use_jk_keys=not enable_search,
    )

    for incident in incidents:
        if incident.id == incident_id:
            return incident.model_dump_json(indent=2)

    return None


async def _provide_rootly_incident_id_or_url(rootly: RootlyPlugin) -> str | None:
    """Prompt user to enter a Rootly incident ID or URL."""
    while True:
        answer = await questionary.text(
            "Enter Rootly incident ID or URL:",
        ).unsafe_ask_async()

        if not answer:
            return None

        incident_id = answer
        if "/" in answer:
            incident_id = [x for x in answer.split("/") if x][-1]

        try:
            incident = await rootly.get_incident_by_id(incident_id)
            return incident.model_dump_json(indent=2)
        except Exception as ex:
            rich.print(f"[red]Failed to retrieve incident with id {incident_id}: {ex}[/red]")
            if not await confirm("Retry with another ID or URL?"):
                return None


async def _select_from_recent_rootly_incidents(
    rootly: RootlyPlugin, incidents_to_consider: int = 20
) -> str | None:
    incidents: list[RootlyIncident] = []
    console = Console()

    with console.status("Fetching recent Rootly incidents...", spinner="dots") as status:
        async for incident_payload in rootly.recent_incident_payloads():
            incidents.append(incident_payload.incident)
            if len(incidents) >= incidents_to_consider:
                break
        status.update("Done 🎉")

    if not incidents:
        rich.print("[yellow]No recent Rootly incidents found.[/yellow]")
        return None

    enable_search = len(incidents) > 10
    incident_id = await select(
        "Select a Rootly incident:",
        choices=[
            Choice(
                f"{incident.attributes.get('title', 'Unknown Title')[:60]}... [{incident.attributes.get('status', 'Unknown')}]"
                if len(incident.attributes.get('title', '')) > 60
                else f"{incident.attributes.get('title', 'Unknown Title')} [{incident.attributes.get('status', 'Unknown')}]",
                value=incident.id,
            )
            for incident in incidents
        ],
        use_search_filter=enable_search,
        use_jk_keys=not enable_search,
    )

    for incident in incidents:
        if incident.id == incident_id:
            return incident.model_dump_json(indent=2)

    return None


async def _use_test_payload_from_agent(agent: Agent) -> str | None:
    """Use a test payload from the agent definition."""
    if not agent.test_payloads:
        return None

    if len(agent.test_payloads) == 1:
        return next(iter(agent.test_payloads.values())).payload

    choices = [
        Choice(test_name, value=payload) for test_name, payload in agent.test_payloads.items()
    ]

    selected_test = await select(
        "Select a test payload:",
        choices=choices,
    )

    return agent.test_payloads[selected_test].payload


async def _provide_json_directly() -> str | None:
    """Prompt user to enter JSON payload directly."""
    rich.print("Enter the JSON payload (press Ctrl+D when done):")
    rich.print("[dim]Tip: You can paste multi-line JSON here[/dim]")

    lines = []
    try:
        while True:
            line = await questionary.text("").unsafe_ask_async()
            if line is None:
                break
            lines.append(line)
    except (EOFError, KeyboardInterrupt):
        pass

    payload_text = "\n".join(lines)

    if not payload_text.strip():
        rich.print("[yellow]No payload provided.[/yellow]")
        return None

    try:
        parsed = json.loads(payload_text)
        return json.dumps(parsed, indent=2)
    except Exception:
        return payload_text


async def _demo_an_incident(agent: Agent, plugin_manager: PluginManager, e: CommandEvents) -> None:
    _panel("Test out your new agent!")
    rich.print(f"You're ready to test the new {agent.name} agent!")
    rich.print(
        "There are many ways to provide an incident for testing. Use the arrows to confirm your preference:"
    )
    rich.print("")

    class PayloadOption(BaseModel):
        title: str
        func: Callable[[], Awaitable[str | None]]

    pd = cast("PagerDutyPlugin", plugin_manager.get_plugin("pagerduty"))
    rootly = cast("RootlyPlugin", plugin_manager.get_plugin("rootly"))

    options = [
        PayloadOption(
            title="Provide a PagerDuty incident ID or URL",
            func=lambda: _provide_incident_id_or_url(pd),
        ),
        PayloadOption(
            title="Select from a list of 20 most recent PagerDuty incidents",
            func=lambda: _select_from_recent_incidents(pd),
        ),
        PayloadOption(
            title="Provide a Rootly incident ID or URL",
            func=lambda: _provide_rootly_incident_id_or_url(rootly),
        ),
        PayloadOption(
            title="Select from a list of 20 most recent Rootly incidents",
            func=lambda: _select_from_recent_rootly_incidents(rootly),
        ),
    ]

    if agent.test_payloads:
        options.insert(
            2,
            PayloadOption(
                title="Run with a test JSON payload from the agent definition",
                func=lambda: _use_test_payload_from_agent(agent),
            ),
        )

    options.append(
        PayloadOption(
            title="Provide the JSON payload directly",
            func=_provide_json_directly,
        )
    )

    selected_option = await select(
        "How would you like to provide the incident?",
        choices=[Choice(opt.title, value=i) for i, opt in enumerate(options)],
    )
    payload = await options[int(selected_option)].func()
    await e.send(
        "payload option selected",
        {"option": options[int(selected_option)].title, "payload_provided": bool(payload)},
    )

    if not payload:
        rich.print("[yellow]No payload provided, skipping the demo.[/yellow]")
        return

    try:
        agent = load_agent(agent.name)
        analysis_agent = AnalysisAgent()
        rich.print("")
        rich.print("Details of the payload we're going to demo:")
        rich.print("-" * 80)
        json_payload = payload
        with contextlib.suppress(json.JSONDecodeError):
            json_payload = json.dumps(json.loads(payload), indent=2)
        payload_lines = json_payload.splitlines()
        if len(payload_lines) > 20:
            display_payload = "...(snipped)...\n" + "\n".join(payload_lines[-20:])
        else:
            display_payload = json_payload
        rich.print(display_payload)

        rich.print("")
        rich.print("> Ready to run the demo agent on this payload?")
        rich.print("")
        await questionary.press_any_key_to_continue().unsafe_ask_async()

        rich.print("> Computing status update... (this may take a minute!)")
        console = Console()
        with console.status("working...", spinner="dots") as status:
            result = await analysis_agent.acall(payload=payload, agent=agent)
            status.update("Done 🎉")
        await e.send("demo complete", {"agent_name_hash": hash_value(agent.name)})

        rich.print("")
        _panel("✅ Agent run complete!")
        rich.print(result)
        rich.print("")
        rich.print("")
        rich.print("You can re-run this demo at any point with:")
        rich.print("")
        rich.print(f"  [bold deep_sky_blue1]unpage agent run {agent.name}[/bold deep_sky_blue1]")
        rich.print("")
    except Exception as ex:
        rich.print(f"[red] Demo failed:[/red] {ex}")
        sys.exit(1)
    await questionary.press_any_key_to_continue(
        message="Ready to wrap up quickstart?"
    ).unsafe_ask_async()
    _panel("🎉 You did it! Next steps")
    rich.print(
        "🎉 You did it! Don't stop now—what do you want to do next? Here are some suggestions below; use the arrow keys to move through each one and see a description."
    )
    rich.print("")
    _ = await select(
        message="Use the arrows to move through the options",
        choices=[
            Choice(
                title="Edit the agent you just ran, or try a different one",
                value="edit_agents",
                description="""You can run `unpage agent -h` to see the full list of available agent commands as you continue to build out your agents



""",
            ),
            Choice(
                title="Learn how to deploy your agent remotely",
                value="learn_to_deploy",
                description="""There are multiple options for deploying your agents. We recommend starting with Guide to Deploying Agents on our docs site. https://docs.unpage.ai/?utm_source=unpage



""",
            ),
            Choice(
                title="Configure more plugins & tools, and build a knowledge graph of your infrastructure",
                value="configure_more",
                description="""Unpage supports a rich infrastructure knowledge graph builder, which can provide helpful context to your Unpage Agents. The graph can be built from your infrastructure tools (like AWS or Aptible) and your observability tools (like Datadog and CloudWatch).

For a full list of our currently-supported Plugins, check out our docs. https://docs.unpage.ai/?utm_source=unpage

If you want to try configuring some more plugins and building the graph, you can run `unpage configure`""",
            ),
        ],
    )
    rich.print(
        "Don't forget to join the Slack community if you haven't already. The Unpage team is always available to answer questions, and you'll be among the first to hear about new updates!"
    )
    rich.print("https://docs.unpage.ai/#learn-more?utm_source=unpage")
    rich.print("")
    rich.print("📖 Docs are at https://docs.unpage.ai/?utm_source=unpage")
    rich.print("")
