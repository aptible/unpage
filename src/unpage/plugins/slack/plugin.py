import inspect
from collections.abc import Callable, Coroutine
from typing import Annotated, Any

import httpx
from fastmcp import FastMCP
from pydantic import BaseModel, Field

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
