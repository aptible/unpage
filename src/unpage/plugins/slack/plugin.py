import inspect
from collections.abc import Callable, Coroutine
from typing import Annotated, Any

import httpx
import questionary
import rich
from fastmcp import FastMCP
from pydantic import BaseModel, Field

from unpage.config import PluginSettings, manager
from unpage.plugins.base import Plugin
from unpage.plugins.mixins import McpServerMixin


class SlackChannel(BaseModel):
    name: str
    description: str
    webhook_url: str


class SlackPluginSettings(BaseModel):
    channels: list[SlackChannel] = Field(default_factory=list)


class SlackPlugin(Plugin, McpServerMixin):
    slack_settings: SlackPluginSettings = Field(default_factory=SlackPluginSettings)

    def init_plugin(self) -> None:
        self.slack_settings = SlackPluginSettings(**self._settings)

    async def interactive_configure(self) -> PluginSettings:
        """Interactive configuration for the Slack plugin.

        Prompts the user to enter one webhook URL, and informs them that
        additional webhooks can be added in the config.yaml file.
        """
        rich.print(
            "[bold]Slack Webhook Configuration[/bold]\n"
            "You can configure one Slack webhook here. To add multiple channels, "
            f"edit ~/.unpage/profiles/{manager.get_active_profile()}/config.yaml after configuration.\n"
        )

        webhook_url = await questionary.text(
            "Slack Webhook URL",
            default="",
            instruction="Get a webhook URL from https://api.slack.com/messaging/webhooks",
        ).unsafe_ask_async()

        channel_name = await questionary.text(
            "Channel Name",
            default="incidents",
            instruction="A descriptive name for this channel (e.g., 'incidents', 'alerts')",
        ).unsafe_ask_async()

        channel_description = await questionary.text(
            "Channel Description",
            default="Post incident updates and alerts",
            instruction="A description of what this channel is used for",
        ).unsafe_ask_async()

        if webhook_url:
            channels = [
                {
                    "name": channel_name,
                    "description": channel_description,
                    "webhook_url": webhook_url,
                }
            ]
        else:
            channels = []

        return {"channels": channels}

    async def validate_plugin_config(self) -> None:
        """Validate the Slack plugin configuration by testing webhook URLs."""
        if not self.slack_settings.channels:
            raise LookupError(
                "No Slack channels configured. Add at least one channel with a webhook URL."
            )

        # Validate each webhook URL
        for channel in self.slack_settings.channels:
            if not channel.webhook_url:
                raise ValueError(f"Webhook URL for channel '{channel.name}' is empty")

            # Validate URL format
            if not channel.webhook_url.startswith("https://hooks.slack.com/"):
                raise ValueError(
                    f"Invalid webhook URL for channel '{channel.name}'. "
                    "Slack webhook URLs should start with 'https://hooks.slack.com/'"
                )

            # Verify webhook URL is reachable without posting a message
            try:
                async with httpx.AsyncClient() as client:
                    # Try HEAD request first (doesn't send a message)
                    response = await client.head(
                        channel.webhook_url,
                        timeout=10.0,
                    )

                    # Slack webhooks may not support HEAD, so if we get 405 (Method Not Allowed)
                    # we'll consider the URL valid as long as the endpoint exists
                    if response.status_code == 404:
                        raise ValueError(
                            f"Webhook URL for channel '{channel.name}' returned 404. "
                            "Please verify the URL is correct."
                        )
                    # Accept 405 (Method Not Allowed) as valid since Slack webhooks only support POST
                    elif response.status_code not in (200, 405):
                        raise ValueError(
                            f"Webhook URL for channel '{channel.name}' returned status {response.status_code}"
                        )

            except httpx.RequestError as e:
                raise ValueError(
                    f"Failed to connect to webhook URL for channel '{channel.name}': {e!s}"
                ) from e

    def get_mcp_server(self) -> FastMCP[Any]:
        mcp = super().get_mcp_server()
        for channel_config in self.slack_settings.channels:
            mcp.tool(self._build_tool_function(channel_config))
        return mcp

    def _build_tool_function(
        self, channel_config: SlackChannel
    ) -> Callable[..., Coroutine[Any, Any, str]]:
        """Create a dynamic MCP tool for posting to a Slack channel."""

        async def _tool_function(message: str, username: str = "Unpage") -> str:
            """Post a message to the Slack channel."""
            payload = {
                "text": message,
                "username": username,
            }

            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        channel_config.webhook_url,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                        timeout=30.0,
                    )
                    response.raise_for_status()

                    if response.text == "ok":
                        return f"Successfully posted message to #{channel_config.name}"
                    else:
                        return f"Slack returned: {response.text}"

            except httpx.HTTPStatusError as e:
                return f"HTTP error posting to #{channel_config.name}: {e.response.status_code} - {e.response.text}"
            except httpx.RequestError as e:
                return f"Request error posting to #{channel_config.name}: {e!s}"
            except Exception as e:
                return f"Unexpected error posting to #{channel_config.name}: {e!s}"

        # Set the function metadata to match the channel config
        tool_name = (
            f"slack_post_to_{channel_config.name.replace('-', '_').replace(' ', '_').lower()}"
        )
        _tool_function.__name__ = tool_name
        _tool_function.__doc__ = (
            f"{channel_config.description} - Post messages to #{channel_config.name} Slack channel"
        )

        # Set the function signature so that FastMCP can inspect it
        _tool_function.__signature__ = inspect.Signature(  # type: ignore
            [
                inspect.Parameter(
                    "message",
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=Annotated[
                        str, Field(description="The message to post to the Slack channel")
                    ],
                ),
                inspect.Parameter(
                    "username",
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    default="Unpage",
                    annotation=Annotated[
                        str,
                        Field(description="Username to display for the message (default: Unpage)"),
                    ],
                ),
            ]
        )

        # Set the function annotations to match the signature
        _tool_function.__annotations__ = {
            "message": Annotated[
                str, Field(description="The message to post to the Slack channel")
            ],
            "username": Annotated[
                str, Field(description="Username to display for the message (default: Unpage)")
            ],
            "return": str,
        }

        return _tool_function
