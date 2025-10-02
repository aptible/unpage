from typing import Any

from fastmcp import Client, FastMCP
from fastmcp.mcp_config import MCPConfig, MCPServerTypes

from unpage.plugins.base import Plugin
from unpage.plugins.mcp.transport import CompositeMCPTransport
from unpage.plugins.mixins.mcp import McpServerMixin


class McpProxyPlugin(Plugin, McpServerMixin):
    """A plugin that proxies MCP requests to a remote MCP server."""

    abstract = True
    prefix_tools: bool = True
    default_enabled: bool = False

    def get_mcp_server_settings(self) -> MCPServerTypes:
        raise NotImplementedError("get_mcp_server_settings must be implemented by subclasses")

    def get_mcp_config(self) -> MCPConfig:
        return MCPConfig(mcpServers={self.name: self.get_mcp_server_settings()})

    def get_mcp_server(self) -> FastMCP[Any]:
        config = self.get_mcp_config()
        if config.mcpServers:
            return FastMCP.as_proxy(
                backend=Client(
                    transport=CompositeMCPTransport(
                        config=config,
                        name_as_prefix=self.prefix_tools,
                    ),
                ),
            )
        return super().get_mcp_server()


class McpPlugin(McpProxyPlugin):
    mcp_servers: dict[str, MCPServerTypes]

    def __init__(
        self,
        *args: Any,
        mcp_servers: dict[str, MCPServerTypes] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.mcp_servers = mcp_servers or {}

    def get_mcp_config(self) -> MCPConfig:
        return MCPConfig(mcpServers=self.mcp_servers)
