from typing import Any, Literal

from fastmcp.mcp_config import MCPServerTypes, RemoteMCPServer, StdioMCPServer

from unpage.plugins.mcp.plugin import McpProxyPlugin


class SentryPlugin(McpProxyPlugin):
    """GitHub plugin."""

    name = "sentry"

    def __init__(
        self,
        *args: Any,
        organization: str,
        mode: Literal["remote", "local"] = "local",
        sentry_token: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.mode = mode
        self.sentry_token = sentry_token

    def get_mcp_server_settings(self) -> MCPServerTypes:
        if self.mode == "local":
            return self._get_local_mcp_server_settings()
        elif self.mode == "remote":
            return self._get_remote_mcp_server_settings()
        else:
            raise ValueError(f"Invalid mode {self.mode!r} (must be 'local' or 'remote')")

    def _get_local_mcp_server_settings(self) -> StdioMCPServer:
        return StdioMCPServer(
            command="npx",
            args=["@sentry/mcp-server"],
            env={
                "SENTRY_ACCESS_TOKEN": self.sentry_token,
            },
        )

    def _get_remote_mcp_server_settings(self) -> RemoteMCPServer:
        return RemoteMCPServer(
            url="https://mcp.sentry.dev/mcp",
            auth="oauth",
        )
