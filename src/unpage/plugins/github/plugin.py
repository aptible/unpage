import os
from typing import Any, Literal

import questionary
from fastmcp.mcp_config import MCPServerTypes, RemoteMCPServer, StdioMCPServer
from questionary import select

from unpage.config import PluginSettings
from unpage.plugins.mcp.plugin import McpProxyPlugin


class GitHubPlugin(McpProxyPlugin):
    """GitHub plugin."""

    name = "github"

    def __init__(
        self,
        *args: Any,
        github_token: str | None = None,
        mode: Literal["remote", "local"] = "local",
        read_only: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.github_token = github_token or os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
        self.mode = mode or os.getenv("GITHUB_MODE", "remote")
        self.read_only = read_only

        if not self.github_token:
            raise ValueError("github_token is required")

    async def interactive_configure(self) -> PluginSettings:
        return {
            "mode": await select(
                "The GitHub plugin uses the GitHub MCP Server for some of its features. Do you want to use the local or remote MCP server?",
                choices=["local", "remote"],
                default=self.mode,
            ).unsafe_ask_async(),
            "github_token": await questionary.password(
                "Enter your GitHub Personal Access Token",
                default=self.github_token or "",
            ).unsafe_ask_async(),
        }

    async def validate_plugin_config(self) -> None:
        """Validate the plugin config."""
        try:
            await super().validate_plugin_config()
            await self.call_tool("github_get_me")
        except Exception as ex:
            raise ValueError(f"Error validating {self.name!r}: {ex}") from ex

    def get_mcp_server_settings(self) -> MCPServerTypes:
        if self.mode == "local":
            return self._get_local_mcp_server_settings()
        elif self.mode == "remote":
            return self._get_remote_mcp_server_settings()
        else:
            raise ValueError(f"Invalid mode {self.mode!r} (must be 'local' or 'remote')")

    def _get_remote_mcp_server_settings(self) -> RemoteMCPServer:
        return RemoteMCPServer(
            transport="http",
            url="https://api.githubcopilot.com/mcp/",
            headers={
                "X-MCP-Readonly": "1" if self.read_only else "0",
            },
            auth=self.github_token or "oauth",
        )

    def _get_local_mcp_server_settings(self) -> StdioMCPServer:
        return StdioMCPServer(
            command="docker",
            args=[
                "run",
                "--rm",
                "-i",
                "-e",
                "GITHUB_PERSONAL_ACCESS_TOKEN",
                "-e",
                "GITHUB_READ-ONLY",
                "ghcr.io/github/github-mcp-server",
            ],
            env={
                "GITHUB_PERSONAL_ACCESS_TOKEN": self.github_token,
                "GITHUB_READ-ONLY": "1" if self.read_only else "0",
            },
        )
