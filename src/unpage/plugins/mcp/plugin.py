import shutil
from typing import Any

from fastmcp import Client, FastMCP
from fastmcp.mcp_config import MCPConfig, MCPServerTypes, StdioMCPServer

from unpage.plugins.base import Plugin
from unpage.plugins.mcp.transport import CompositeMCPTransport
from unpage.plugins.mixins.mcp import McpServerMixin
from unpage.utils import suppress_output


class McpProxyPlugin(Plugin, McpServerMixin):
    """A plugin that proxies MCP requests to a remote MCP server."""

    abstract = True
    prefix_tools: bool = True
    default_enabled: bool = False

    async def validate_plugin_config(self) -> None:
        """Validate the plugin config."""
        config = self.get_mcp_config()
        for name, server in config.mcpServers.items():
            # Validate that the configured command is in the PATH
            if isinstance(server, StdioMCPServer) and not shutil.which(server.command):
                raise ValueError(f"Command {server.command!r} not found in PATH")

            # Attempt to connect to the server as a simple auth check.
            #
            # Note, however, than many MCP servers will allow you to connect
            # even with invalid credentials, and may only throw auth-related
            # errors when calling tools or accessing resources.
            #
            # Individual plugins are encouraged to override this method and
            # provide additional validation.
            with suppress_output():
                try:
                    async with Client(
                        self.get_mcp_server(MCPConfig(mcpServers={name: server}))
                    ) as client:
                        if not client.is_connected():
                            raise ValueError(
                                f"Unable to connect to server {name!r}. Are your credentials correct?"
                            )
                except Exception as ex:
                    raise ValueError(f"Error connecting to server {name!r}: {ex}") from ex

    def get_mcp_server_settings(self) -> MCPServerTypes:
        """Return an MCP server settings for the proxy server."""
        raise NotImplementedError("get_mcp_server_settings must be implemented by subclasses")

    def get_mcp_config(self) -> MCPConfig:
        """Return an MCP config for the proxy server."""
        return MCPConfig(mcpServers={self.name: self.get_mcp_server_settings()})

    def get_mcp_server(self, config: MCPConfig | None = None) -> FastMCP[Any]:
        """Return an MCP proxy server for the given config."""
        config = config or self.get_mcp_config()

        if not config.mcpServers:
            return super().get_mcp_server()

        return FastMCP.as_proxy(
            backend=Client(
                transport=CompositeMCPTransport(
                    config=config,
                    name_as_prefix=self.prefix_tools,
                ),
            ),
        )

    def get_mcp_client(self, config: MCPConfig | None = None) -> Client[Any]:
        """Return an MCP client for the given config."""
        return Client(self.get_mcp_server(config or self.get_mcp_config()))

    async def list_tools(self) -> list[str]:
        """List the tools available on the MCP server."""
        async with self.get_mcp_client() as client:
            return [tool.name for tool in await client.list_tools()]

    async def call_tool(self, tool_name: str, *args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        """Call an MCP tool."""
        async with self.get_mcp_client() as client:
            return await client.call_tool(tool_name, *args, **kwargs)


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
