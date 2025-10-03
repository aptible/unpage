from typing import Any

from fastmcp import FastMCP
from fastmcp.contrib.mcp_mixin import (
    MCPMixin,
    mcp_prompt,
    mcp_resource,
    mcp_tool,
)

from unpage.plugins import PluginCapability


class McpServerMixin(MCPMixin, PluginCapability):
    """Capability for registering tools, resources, and prompts with the MCP server."""

    def register_all(self, mcp_server: FastMCP[Any], *args: Any, **kwargs: Any) -> None:
        # Register any existing resources, as usual.
        super().register_all(mcp_server, *args, **kwargs)

        # Mount the MCP sub-server
        mcp_server.mount(self.get_mcp_server())

    def get_mcp_server(self) -> FastMCP[Any]:
        return FastMCP[Any](self.name)


prompt = mcp_prompt
resource = mcp_resource
tool = mcp_tool
