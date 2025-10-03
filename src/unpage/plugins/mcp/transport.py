from typing import TYPE_CHECKING, Any

from fastmcp import FastMCP
from fastmcp.client.transports import FastMCPTransport, MCPConfigTransport
from fastmcp.mcp_config import MCPConfig
from fastmcp.utilities.mcp_config import mcp_config_to_servers_and_transports

if TYPE_CHECKING:
    from fastmcp.client import ClientTransport


class CompositeMCPTransport(MCPConfigTransport):
    """A transport that composes multiple MCP servers into a single transport.

    This is a slightly-modified version of the MCPConfigTransport, because the
    original implementation only prefixed tools if there was more than one MCP
    server configured.
    """

    def __init__(self, config: MCPConfig | dict, name_as_prefix: bool = True) -> None:
        self.config = config if isinstance(config, MCPConfig) else MCPConfig.from_dict(config)
        self._underlying_transports: list[ClientTransport] = []

        if not self.config.mcpServers:
            raise ValueError("No MCP servers defined in the config")

        name = FastMCP.generate_name("MCPRouter")
        self._composite_server = FastMCP[Any](name=name)

        for name, server, transport in mcp_config_to_servers_and_transports(self.config):
            self._underlying_transports.append(transport)
            self._composite_server.mount(server, prefix=name if name_as_prefix else None)

        self.transport = FastMCPTransport(mcp=self._composite_server)
