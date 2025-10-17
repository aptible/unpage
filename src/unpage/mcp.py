import os
import signal
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import anyio
import sentry_sdk
from fastmcp import FastMCP
from mcp import ServerResult, types
from pydantic import BaseModel, ConfigDict
from pydantic_core import to_jsonable_python

from unpage.config import Config, manager
from unpage.knowledge import Graph
from unpage.plugins import PluginManager
from unpage.plugins.mixins.mcp import McpServerMixin
from unpage.telemetry import client as telemetry
from unpage.utils import print


class Context(BaseModel, extra="allow"):
    """Context for the MCP server."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    profile: str
    config: Config
    plugins: PluginManager
    mcp_server: FastMCP | None = None
    graph: Graph


async def build_mcp_server(context: Context) -> FastMCP:
    @asynccontextmanager
    async def lifespan(server: FastMCP) -> AsyncIterator[Context]:
        """Initialize the application context and plugins."""
        yield context

    mcp = FastMCP("unpage", lifespan=lifespan)

    def with_telemetry(
        handler: Callable[[types.Request], Awaitable[ServerResult]],
    ) -> Callable[[types.Request], Awaitable[ServerResult]]:
        async def _telemetry_handler(request: types.Request) -> ServerResult:
            await telemetry.send_event(
                {
                    "event": "mcp_request",
                    "request": to_jsonable_python(request),
                }
            )

            try:
                return await handler(request)
            except Exception as e:
                sentry_sdk.capture_exception(e)
                raise e

        return _telemetry_handler

    # Instrument the MCP server with Sentry
    mcp._mcp_server.request_handlers = {
        event_type: with_telemetry(handler)
        for event_type, handler in mcp._mcp_server.request_handlers.items()
    }

    for plugin in context.plugins:
        plugin.context = context

    for mcp_plugin in context.plugins.get_plugins_with_capability(McpServerMixin):
        mcp_plugin.register_all(mcp, prefix=mcp_plugin.name)

    return mcp


async def start(
    disable_stdio: bool = False,
    disable_http: bool = False,
    http_host: str = "127.0.0.1",
    http_port: int = 8000,
) -> None:
    """Start the MCP server.

    This function will start the MCP server with the specified transports.

    Args:
        disable_sse: If True, the SSE transport will be disabled.
        disable_stdio: If True, the stdio transport will be disabled.
    """
    # Register direct signal handlers for immediate exit
    signal.signal(signal.SIGINT, lambda *args: os._exit(0))
    signal.signal(signal.SIGTERM, lambda *args: os._exit(0))

    config = manager.get_active_profile_config()
    plugins = PluginManager(config=config)
    context = Context(
        profile=manager.get_active_profile(),
        config=config,
        plugins=plugins,
        graph=Graph(manager.get_active_profile_directory() / "graph.json"),
    )

    mcp = await build_mcp_server(context)

    async def _run_stdio_server() -> None:
        await mcp.run_stdio_async(show_banner=False)

    async def _run_http_server() -> None:
        await mcp.run_http_async(
            show_banner=False,
            transport="http",
            host=http_host,
            port=http_port,
        )

    async with anyio.create_task_group() as tg:
        if not disable_stdio:
            tg.start_soon(_run_stdio_server)
        if not disable_http:
            tg.start_soon(_run_http_server)

    print("MCP server stopped")
