from typing import Any

from fastmcp import FastMCP
from fastmcp.mcp_config import MCPConfig, MCPServerTypes
from pydantic import Field

from unpage.plugins.base import Plugin
from unpage.plugins.mixins.mcp_proxy import McpProxyMixin


class McpproxyPlugin(Plugin, McpProxyMixin):
    mcp_servers: dict[str, MCPServerTypes] = Field(
        description="Standard configuration for MCP servers", default_factory=dict
    )

    def __init__(
        self, *args: Any, mcp_servers: dict[str, MCPServerTypes] | None = None, **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self.mcp_servers = mcp_servers if mcp_servers else {}

    async def get_mcp_server_to_import(self) -> FastMCP[Any]:
        if not self.mcp_servers:
            return FastMCP[Any](self.name)
        return FastMCP.as_proxy(
            MCPConfig(mcpServers=self.mcp_servers), name="Unpage Proxy MCP Servers"
        )
