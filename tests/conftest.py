from collections.abc import AsyncGenerator

import pytest_asyncio
from fastmcp import Client, FastMCP

from unpage.config.utils import Config
from unpage.knowledge import Graph
from unpage.mcp import Context, build_mcp_server
from unpage.plugins import PluginManager


@pytest_asyncio.fixture
async def default_config() -> Config:
    return PluginManager.default_config


@pytest_asyncio.fixture
async def mcp_server(default_config: Config) -> FastMCP:
    plugins = PluginManager(config=default_config)
    server = await build_mcp_server(
        Context(
            profile="test",
            config=default_config,
            plugins=plugins,
            graph=Graph(),
        )
    )

    return server


@pytest_asyncio.fixture
async def mcp_client(mcp_server: FastMCP) -> AsyncGenerator[Client, None]:
    async with Client(mcp_server) as client:
        yield client
