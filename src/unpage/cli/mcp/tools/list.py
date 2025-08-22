from unpage.cli.mcp.tools._app import tools_app
from unpage.config import manager
from unpage.knowledge import Graph
from unpage.mcp import Context, build_mcp_server
from unpage.plugins import PluginManager
from unpage.telemetry import client as telemetry
from unpage.telemetry import prepare_profile_for_telemetry


@tools_app.command(name="list")
async def list_tools() -> None:
    """List all MCP tools available from enabled plugins."""
    await telemetry.send_event(
        {
            "command": "mcp tools list",
            **prepare_profile_for_telemetry(manager.get_active_profile()),
        }
    )
    config = manager.get_active_profile_config()
    plugins = PluginManager(config=config)
    context = Context(
        profile=manager.get_active_profile(),
        config=config,
        plugins=plugins,
        graph=Graph(manager.get_active_profile_directory() / "graph.json"),
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
