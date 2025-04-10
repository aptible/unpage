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

    def get_mcp_server(self) -> FastMCP[Any]:
        mcp = FastMCP[Any](self.name)
        self.register_all(mcp)
        return mcp


prompt = mcp_prompt
resource = mcp_resource
tool = mcp_tool
