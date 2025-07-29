import json
from typing import Annotated

import anyio
import typer
from fastmcp import Client
from mcp.types import TextContent

from unpage.cli.mcp.tools._app import tools_app
from unpage.cli.options import PROFILE_OPTION
from unpage.config import load_config
from unpage.config.utils import get_config_dir
from unpage.knowledge import Graph
from unpage.mcp import Context, build_mcp_server
from unpage.plugins import PluginManager
from unpage.telemetry import client as telemetry
from unpage.telemetry import prepare_profile_for_telemetry


@tools_app.command()
def call(
    tool: str,
    count_results: Annotated[
        bool,
        typer.Option(
            "--count-results",
            "-c",
            help="Count the number of results returned by the tool instead of printing the results (works best with list or dict tool responses)",
        ),
    ] = False,
    count_level: Annotated[
        int, typer.Option("--count-level", help="Count level for nested structures", min=0, max=1)
    ] = 0,
    arguments: Annotated[list[str] | None, typer.Argument()] = None,
    profile: str = PROFILE_OPTION,
) -> None:
    """Call an MCP tool from the command line."""

    async def _call_tool() -> None:
        await telemetry.send_event(
            {
                "command": "mcp tools call",
                "tool": tool,
                **prepare_profile_for_telemetry(profile),
                "count_results": count_results,
                "count_level": count_level,
                "has_arguments": arguments is not None,
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
        if tool not in tools:
            raise typer.Abort(f"Tool {tool} not found")

        tool_def = tools[tool]
        tool_args = {}
        if arguments:
            # Convert a list of arguments into a dict
            for k, v in zip(tool_def.parameters["properties"].keys(), arguments, strict=True):
                # Try decoding as JSON to handle complex arguments (lists, dicts, etc.)
                try:
                    tool_args[k] = json.loads(v)
                except json.JSONDecodeError:
                    tool_args[k] = v

        client = Client(mcp)
        async with client:
            result = await client.call_tool(tool, tool_args)
            try:
                content = next(r.text for r in result.content if isinstance(r, TextContent))
                if count_results and count_level == 0:
                    print(
                        json.dumps(
                            {"count": len(json.loads(content)), "content_length": len(content)},
                            indent=2,
                        )
                    )
                elif count_results and count_level == 1:
                    print(
                        json.dumps(
                            {
                                k: (
                                    {
                                        "count": len(v),
                                        "content_length": len(json.dumps(v)),
                                    }
                                    if isinstance(v, list | dict)
                                    else v
                                )
                                for k, v in json.loads(content).items()
                            },
                            indent=2,
                        )
                    )
                else:
                    print(content)
            except StopIteration:
                print(f"{tool} returned no printable results")

    anyio.run(_call_tool)
