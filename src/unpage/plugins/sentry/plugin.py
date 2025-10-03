import os
from typing import Any, Literal

import questionary
from fastmcp.mcp_config import MCPServerTypes, RemoteMCPServer, StdioMCPServer
from questionary import select

from unpage.config import PluginSettings
from unpage.plugins.mcp.plugin import McpProxyPlugin


class SentryPlugin(McpProxyPlugin):
    """Sentry plugin."""

    name = "sentry"

    def __init__(
        self,
        *args: Any,
        mode: Literal["remote", "local"] | None = None,
        sentry_token: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.mode = mode or os.getenv("SENTRY_MODE", "remote")
        self.sentry_token = sentry_token or os.getenv("SENTRY_TOKEN")

        if self.mode == "local" and not self.sentry_token:
            raise ValueError("sentry_token is required when mode is 'local'")

    async def interactive_configure(self) -> PluginSettings:
        mode = await select(
            "The Sentry plugin uses the Sentry MCP Server for some of its features. Do you want to run the MCP server locally, or use Sentry's hosted MCP server?",
            choices=["local", "remote"],
            default=self.mode,
        ).unsafe_ask_async()

        sentry_token = (
            await questionary.password(
                "Enter your Sentry API token",
                default=self.sentry_token or "",
            ).unsafe_ask_async()
            if mode == "local"
            else None
        )

        return {
            "mode": mode,
            "sentry_token": sentry_token,
        }

    async def validate_plugin_config(self) -> None:
        """Validate the plugin config."""
        try:
            await super().validate_plugin_config()
            await self.call_tool("sentry_whoami")
        except Exception as ex:
            raise ValueError(f"Error validating {self.name!r}: {ex}") from ex

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
