import asyncio
import os
import shlex
import sys
from pathlib import Path
from typing import Annotated, Any

import anyio
from cyclopts import Parameter
import questionary
import rich

from unpage.cli._app import app
from unpage.cli.options import DEFAULT_PROFILE, ProfileParameter
from unpage.config.utils import Config, PluginConfig, load_config, save_config
from unpage.plugins.base import PluginManager
from unpage.telemetry import client as telemetry
from unpage.telemetry import prepare_profile_for_telemetry
from unpage.utils import Choice, checkbox, confirm


def _resolve_default_use_uv_run() -> bool:
    try:
        cwd = Path.cwd()
        git_dir = None
        for parent in [cwd, *cwd.parents[:10]]:
            if (parent / ".git").exists():
                git_dir = parent
                break
        if git_dir is None:
            return False
        repo_name = git_dir.name
        return repo_name == "unpage"
    except Exception:
        return False


_default_use_uv_run = _resolve_default_use_uv_run()


async def _send_event(step: str, profile: str, extra_params: dict[Any, Any] | None = None) -> None:
    await telemetry.send_event(
        {
            "command": "configure",
            "step": step,
            **prepare_profile_for_telemetry(profile),
            **(extra_params if extra_params else {}),
        }
    )


@app.command
def configure(
    *,
    profile: Annotated[str, ProfileParameter] = DEFAULT_PROFILE,
    use_uv_run: bool = _default_use_uv_run,
) -> None:
    """Setup unpage including all plugins!

    Parameters
    ----------
    profile
        The profile to use
    use_uv_run
        Use uv run instead of uvx to start the Unpage MCP server (useful for developing Unpage)
    """

    async def _recipe() -> None:
        await _send_event(
            "start",
            profile,
            extra_params={
                "use_uv_run": use_uv_run,
            },
        )
        welcome_to_unpage()
        await _configure_intro()
        cfg = _initial_config(profile)
        await _select_plugins_to_enable_disable(cfg)
        save_config(cfg, profile, create=True)
        await _send_event("config_saved", profile)
        rich.print("")
        await _configure_plugins(cfg, profile)
        await _send_event("plugins_configured", profile)
        save_config(cfg, profile, create=True)
        await _send_event("config_saved_2", profile)
        rich.print("")
        await _suggest_building_graph(profile, use_uv_run)

    anyio.run(_recipe)


def welcome_to_unpage() -> None:
    rich.print("""
                      [deep_sky_blue1]                        -@@@@@%%%%+       [/deep_sky_blue1]
                      [deep_sky_blue1]                             :+@@@*       [/deep_sky_blue1]
                      [deep_sky_blue1]             %@@@@@@%       +@@#-         [/deep_sky_blue1]
                      [deep_sky_blue1]                 %@*     :%@@#            [/deep_sky_blue1]
                      [deep_sky_blue1]     =*%%-     +@%:     #%@@#+.           [/deep_sky_blue1]
                      [deep_sky_blue1]   -=-=%#     #@@+---    -=+*#%%@%        [/deep_sky_blue1]
                      [deep_sky_blue1]     .%+      +##****                     [/deep_sky_blue1]
                      [deep_sky_blue1]     %@@@@=                               [/deep_sky_blue1]
                                                .-+#%%%%%%#:
                              :--==+#%%@%#*=-::..      ..  :%+
                .=+**##%%%%*=:.      .:-+***##%%%*+++++:%@%: =#
            *%#+:       :+#%%%%%%%##*+==*#%%###*+:     +#+@@# =%
         .##: :*%%%%#*###+++*#*++==-.                   .*#@@* **
       -%@# -%@@%*##=:.                                  =*%@@+ %=
      %@@@+ #@@@=%        [bright_green]                        .%  [/bright_green]    *+@@@: %.
     %@@@@# *@@@%#:       [bright_green]                   +*   =@. [/bright_green]    :%*@@@.:*
    -@@@@@%..@@@@=+       [bright_green]  +:    %=          =%##%=  [/bright_green]     +##@@%.++
    -@@@@@@# *@@@%+:      [bright_green]  :%*. *%.                  [/bright_green]      %#%@@*.#:
     %@@@@@@- %@@%*+      [bright_green]    .+*-           :+       [/bright_green]       **@@%.-@
     =@@@@@@% :%@@*+.     [bright_green]            -#-..:+%-       [/bright_green]       %#%@@* *#
      #@@@@@@* +@@%+*     [bright_green]               --:          [/bright_green]   .=*%#%@@@@= #=
      =@@@@@@%..%@@#*+                        .-+#%%%%###%%@@@@@@@@@: %.
       #@@@@@@+ *@@@-#:           .:-+*###**#**+*#%@%%#+=-+%.    .+%@ -#
       -%@@@@@%: @@@@-+*+++**##*+++*#**#%@@@@@@@%+..:-=*#- #-.+.=#:-@* *=
        #@@@%@@# =@@@@@%%%%%%%@@@@@@%%%%@@@@@@@+.%%%.   @% =# .  .+ #%-:%
         @@@@%%@= %@@@%***+=--==+*%%%%%#+:-%@@@* +%%+-. %@: % -=++ .@%- %.
         -@@* .%@ .%@ +%%+-:.         +@@@* %@%%#=.   ..    #=   =#@@# :%.
          #*   #@# -@=.%+        -+*##%@%+ .@@@@@%%@@@@@@@@@@@@@@%%#.  **
          %   -@@@- *@* .*#######*=     .*%%@@@@@@@@%%%##*-       .=*+%*
         =+   %@@@#  %@@@*:..::-=*%@@%@@@@%#++=-:    .:-=+#%@@@@%@@@@%=
         #-   @@@%@#  -%@@@@@@@%#+-..     :=+**#%%@@@@@@@@@@@@@@@@@@#
         #-   @@@@%@@%-        :=#%%@@@@@@@@@@@*      -%@@@@@@*   -%
         +#   #@@@@@@%%@@@@@@@@@@%@%*      *%@@@@@#**#=  .+%%- =%*-%
          #+   :+%@@%@@@@@@@@@@@@@@@@%@%*:   =%@#     #%#: #-.%@@%*%
          :%        #@@@@@@@@@@@@@@%%##%@@%=  -%. *%+ #@@@@# %@@%*%:
           +%   +  + *@%###+-.           +%@%%%= *@@=-# -%@@@@@%*%-
             +%- -*.#%+                    =%@@=*@@#.*    #@@@@%*
               :**=-.                        *@@@@#+*        .
                                               *%%+

              ██╗   ██╗███╗   ██╗██████╗  █████╗  ██████╗ ███████╗
              ██║   ██║████╗  ██║██╔══██╗██╔══██╗██╔════╝ ██╔════╝
              ██║   ██║██╔██╗ ██║██████╔╝███████║██║  ███╗█████╗
              ██║   ██║██║╚██╗██║██╔═══╝ ██╔══██║██║   ██║██╔══╝
              ╚██████╔╝██║ ╚████║██║     ██║  ██║╚██████╔╝███████╗
               ╚═════╝ ╚═╝  ╚═══╝╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚══════╝

> Welcome to Unpage!""")


async def _configure_intro() -> None:
    rich.print(""">
> This interactive tool will setup Unpage plugins so you'll be ready to:
>
>   • Build a knowlege graph of your infrastructure
>   • Use Unpage's MCP server tools to interact with your graph, logs, and metrics
>   • Write your own agents using everything above!
> """)
    rich.print("> Ready to start?")
    rich.print("")
    await questionary.press_any_key_to_continue().unsafe_ask_async()


def _initial_config(profile: str) -> Config:
    default_config = PluginManager.default_config
    try:
        existing_config = load_config(profile, create=False)
    except Exception:
        existing_config = default_config
    plugin_settings: dict[str, PluginConfig] = {}
    for plugin_name in default_config.plugins:
        plugin_settings[plugin_name] = PluginConfig(
            enabled=(
                default_config.plugins[plugin_name].enabled
                if plugin_name not in existing_config.plugins
                else existing_config.plugins[plugin_name].enabled
            ),
            settings=(
                default_config.plugins[plugin_name].settings
                if plugin_name not in existing_config.plugins
                else existing_config.plugins[plugin_name].settings
            ),
        )
    return Config(plugins=plugin_settings)


async def _select_plugins_to_enable_disable(
    cfg: Config,
) -> None:
    rich.print("")
    rich.print("> 1. Select plugins")
    rich.print("")
    rich.print(
        "> Unpage uses plugins to access your infrastructure resources, like AWS or Aptible."
    )
    rich.print("> Each plugin may be enabled or disabled to match your desired knowledge graph")
    rich.print(
        "> Some plugins require configuration, for example the AWS plugin needs access to your AWS account"
    )
    rich.print("")
    rich.print("> These pre-selected plugins are the one we recommend:")
    rich.print("")
    await _enable_disable_plugins(cfg)
    rich.print("")
    rich.print("> Great! We'll setup these plugins:")
    rich.print(">")
    rich.print(f">   {', '.join(sorted([p for p in cfg.plugins if cfg.plugins[p].enabled]))}")
    rich.print(">")


async def _enable_disable_plugins(cfg: Config) -> None:
    possible_plugins = list(cfg.plugins.keys())
    enabled_search = len(possible_plugins) > 10
    rich.print("")
    selected_plugins = await checkbox(
        "Which plugins would you like to enable? Press enter to continue",
        choices=[Choice(p, checked=True) for p in cfg.plugins],
        use_search_filter=enabled_search,
        use_jk_keys=not enabled_search,
    )
    for plugin_name in cfg.plugins:
        cfg.plugins[plugin_name].enabled = plugin_name in selected_plugins
    rich.print("")


async def _configure_plugins(cfg: Config, profile: str) -> None:
    rich.print("> 2. Configure plugins")
    rich.print("")
    rich.print("> Now we will go through each plugin and configure it.")
    rich.print(
        "> We will run validation for each plugin, and if something doesn't work you'll have a chance to retry the configuration."
    )
    rich.print(
        "> You can stop the retries, even if the validation is failing, and we'll move to the next plugin."
    )
    rich.print("")
    rich.print("> Ready to start plugin configuration and validation?")
    rich.print("")
    await questionary.press_any_key_to_continue().unsafe_ask_async()
    rich.print("")
    plugin_manager = PluginManager(cfg)
    for plugin_name in cfg.plugins:
        if not cfg.plugins[plugin_name].enabled:
            await _send_event(f"plugin_disabled_{plugin_name}", profile)
            continue
        attempts = 1
        while True:
            rich.print(f"> [bold]{plugin_name}[/bold] plugin configuration:")
            rich.print("")
            cfg.plugins[plugin_name].settings = await plugin_manager.get_plugin(
                plugin_name
            ).interactive_configure()
            plugin_manager = PluginManager(cfg)
            if await _plugin_valid(plugin_manager, plugin_name):
                await _send_event(
                    f"plugin_valid_{plugin_name}", profile, extra_params={"attempts": attempts}
                )
                break
            rich.print(f"> Validation failed for {plugin_name}")
            if not await confirm("Retry?"):
                await _send_event(
                    f"plugin_invalid_{plugin_name}", profile, extra_params={"attempts": attempts}
                )
                break
            attempts += 1
            rich.print("")
        rich.print("")
    rich.print("> Wooooo you did it! All the plugins are configured and ready to use!")
    rich.print("")
    rich.print("> Ready to move on?")
    rich.print("")
    await questionary.press_any_key_to_continue().unsafe_ask_async()
    rich.print("")


async def _plugin_valid(plugin_manager: PluginManager, plugin_name: str) -> bool:
    rich.print(f"> Validating {plugin_name}...")
    try:
        await plugin_manager.get_plugin(plugin_name).validate_plugin_config()
    except Exception as ex:
        rich.print(f"Error validating {plugin_name}:\n{ex}")
        return False
    rich.print(f"[green]{plugin_name} configuration is valid![/green]")
    return True


async def _suggest_building_graph(profile: str, use_uv_run: bool) -> None:
    rich.print("> 3. Next steps")
    rich.print("")
    rich.print("> Now you're all set to build the infrastructure knowledge graph.")
    rich.print(
        "> The infrastructure knowledge graph is a directed graph of nodes and edges that represent your infra."
    )
    rich.print(
        "> Nodes are resources like ec2 instances, databases, load balancers, and much more."
    )
    rich.print("> Edges represent a directional relationship between two nodes.")
    rich.print("")
    rich.print(
        "> The knowledge graph is a powerful tool for agents to use when investigating incidents!"
    )
    rich.print("")
    rich.print("> Create the graph by running:")
    rich.print(">")
    rich.print(
        f">   {'uvx' if not use_uv_run else 'uv run'} unpage graph build{f' --profile {profile}' if profile != DEFAULT_PROFILE else ''}"
    )
    rich.print(">")
    rich.print("> This is full usage for `unpage graph build`:")
    rich.print("")
    graph_build_cmd = " ".join([a if a != "configure" else "graph build" for a in sys.argv])
    rich.print("> $ unpage graph build --help")
    rich.print("")
    await (await asyncio.create_subprocess_shell(f"{graph_build_cmd} --help")).wait()
    rich.print("")
    rich.print(">")
    if not await confirm(
        "Would you like to launch `unpage graph build` now? (this can take 5min or up to an hour, or even more, depending on how large your infra is)"
    ):
        await _send_event("done_no_graph_build", profile)
        return
    rich.print(">")
    await _send_event("starting_graph_build", profile)
    _replace_current_proc_with_unpage_graph_build(graph_build_cmd)


def _replace_current_proc_with_unpage_graph_build(graph_build_cmd: str) -> None:
    rich.print("> Running: unpage graph build")
    rich.print("")
    cmd = shlex.split(graph_build_cmd)
    os.execvp(cmd[0], cmd)  # noqa: S606 Starting a process without a shell
