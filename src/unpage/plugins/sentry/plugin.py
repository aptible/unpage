from typing import Any

import httpx
from fastmcp import Client, FastMCP
from fastmcp.client.auth.oauth import ClientNotFoundError, OAuth
from fastmcp.mcp_config import MCPConfig, MCPServerTypes, RemoteMCPServer
from pydantic import Field

from unpage.config import PluginSettings
from unpage.plugins.base import Plugin
from unpage.plugins.mcp.plugin import CompositeMCPTransport
from unpage.plugins.mixins.mcp import McpServerMixin


class SentryOAuth(OAuth):
    """OAuth client for Sentry with enhanced error handling."""

    async def redirect_handler(self, authorization_url: str) -> None:
        """Override redirect handler to fix OAuth flow for Sentry."""

        # Pre-flight check to detect invalid client_id before opening browser
        async with httpx.AsyncClient() as client:
            response = await client.get(authorization_url, follow_redirects=False)
            if response.status_code == 400:
                raise ClientNotFoundError(
                    "OAuth client not found - cached credentials may be stale"
                )

        import webbrowser

        webbrowser.open(authorization_url)


class SentryPlugin(Plugin, McpServerMixin):
    """A plugin for Sentry error monitoring that connects to Sentry's hosted MCP server."""

    organization: str | None = Field(
        description="Sentry organization slug (optional, can be configured during OAuth)",
        default=None,
    )

    def __init__(
        self,
        *args: Any,
        organization: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.organization = organization

    async def interactive_configure(self) -> PluginSettings:
        """Interactive wizard for configuring the Sentry plugin."""
        import questionary

        organization = await questionary.text(
            "Enter your Sentry organization slug (optional, can be set during OAuth)",
            default=self.organization or "",
            instruction="This can be left blank and configured during the OAuth flow",
        ).unsafe_ask_async()

        return {
            "organization": organization if organization else None,
        }

    def init_plugin(self) -> None:
        """Initialize the plugin."""
        super().init_plugin()

    async def validate_plugin_config(self) -> None:
        """Validate the plugin configuration.

        For OAuth-based authentication, validation will happen during the OAuth flow,
        so we don't need to validate much here.
        """
        pass

    def get_mcp_server(self) -> FastMCP[Any]:
        """Return the MCP server configured for Sentry's hosted MCP server with OAuth."""
        mcp_config = self._get_sentry_mcp_config()

        transport = CompositeMCPTransport(
            config=MCPConfig(mcpServers=mcp_config),
            name_as_prefix=False,
        )

        return FastMCP.as_proxy(
            backend=Client(transport=transport),
            name="Sentry Error Monitoring",
        )

    def _get_sentry_mcp_config(self) -> dict[str, MCPServerTypes]:
        """Get the Sentry MCP server configuration."""
        oauth_client = SentryOAuth(
            mcp_url="https://mcp.sentry.dev/mcp",
            client_name="Unpage Sentry Plugin",
        )

        return {
            "sentry": RemoteMCPServer(
                url="https://mcp.sentry.dev/mcp",
                auth=oauth_client,
            )
        }
