from typing import Any, Literal

from fastmcp.mcp_config import MCPServerTypes, RemoteMCPServer, StdioMCPServer

from unpage.plugins.mcp.plugin import McpProxyPlugin


class GitHubPlugin(McpProxyPlugin):
    """GitHub plugin."""

    name = "github"

    def __init__(
        self,
        *args: Any,
        github_token: str,
        mode: Literal["remote", "local"] = "local",
        read_only: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.github_token = github_token
        self.mode = mode
        self.read_only = read_only

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
                "Authorization": f"Bearer {self.github_token}",
                "X-MCP-Readonly": "1" if self.read_only else "0",
            },
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
