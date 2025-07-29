import anyio

from unpage.cli.mcp.tools._app import tools_app
from unpage.cli.options import PROFILE_OPTION
from unpage.config import load_config
from unpage.config.utils import get_config_dir
from unpage.knowledge import Graph
from unpage.mcp import Context, build_mcp_server
from unpage.plugins import PluginManager
from unpage.telemetry import client as telemetry
from unpage.telemetry import prepare_profile_for_telemetry


@tools_app.command("list")
def list_tools(
    profile: str = PROFILE_OPTION,
) -> None:
    """List all MCP tools available from enabled plugins."""

    async def _list_tools() -> None:
        await telemetry.send_event(
            {
                "command": "tools list",
                **prepare_profile_for_telemetry(profile),
            }
        )
        config = load_config(profile)
        plugins = PluginManager(config=config)
        context = Context(
            profile=profile,
            config=config,
            plugins=plugins,
            graph=Graph(get_config_dir(profile) / "graph.json"),
        )
        mcp = await build_mcp_server(context)

        tools = await mcp.get_tools()
        for key, tool in tools.items():
            cmd = [key]
            for arg, arg_data in tool.parameters["properties"].items():
                arg_type = arg_data.get("type", "unknown")
                if "anyOf" in arg_data:
                    arg_type = "|".join(t["type"] for t in arg_data["anyOf"])
                cmd.append(f"<{arg}:{arg_type}>")
            print(" ".join(cmd))

    anyio.run(_list_tools)
