from typing import Any

from fastmcp import FastMCP

from unpage.plugins import PluginCapability


class McpProxyMixin(PluginCapability):
    """Capability for registering proxied MCP servers"""

    def get_mcp(self) -> FastMCP[Any]:
        """Creates a base FastMCP server for further configuration"""
        return FastMCP[Any](self.name)

    async def get_mcp_server_to_import(self) -> FastMCP[Any]:
        raise NotImplementedError(
            f"{self.name} plugin: must implement get_mcp_server_to_import method to be McpProxyMixin"
        )
