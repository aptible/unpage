import asyncio
import inspect
import shlex
from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from unpage.plugins.base import Plugin
from unpage.plugins.mixins import McpServerMixin


class ShellCommand(BaseModel):
    handle: str
    description: str
    command: str
    args: dict[str, str] = Field(default_factory=dict)


class ShellPluginSettings(BaseModel):
    commands: list[ShellCommand] = Field(default_factory=list)


class ShellPlugin(Plugin, McpServerMixin):
    shell_settings: ShellPluginSettings = Field(default_factory=ShellPluginSettings)

    def init_plugin(self) -> None:
        self.shell_settings = ShellPluginSettings(**self._settings)

    def get_mcp_server(self) -> FastMCP[Any]:
        mcp = super().get_mcp_server()
        for command_config in self.shell_settings.commands:
            mcp.tool(self._build_tool_function(command_config))
        return mcp

    def _build_tool_function(
        self, command_config: ShellCommand
    ) -> Callable[..., Coroutine[Any, Any, str]]:
        """Create a dynamic MCP tool for a shell command."""

        # Create an anonymous function that executes the command.
        async def _tool_function(*args: str, **kwargs: str) -> str:
            escaped_args = {k: shlex.quote(v) for k, v in kwargs.items()}
            rendered_command = command_config.command.format(**escaped_args)

            process = await asyncio.create_subprocess_shell(
                rendered_command,
                # Combine stdout and stderr into a single stream
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await process.communicate()
            result = stdout.decode()

            if process.returncode != 0:
                return f"Command returned non-zero code {process.returncode}: {result}"

            return result

        # Set the function metadata to match the command config.
        _tool_function.__name__ = command_config.handle
        _tool_function.__doc__ = command_config.description

        # Set the function signature so that FastMCP can inspect it.
        _tool_function.__signature__ = inspect.Signature(  # type: ignore
            [
                inspect.Parameter(
                    arg_name,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=Annotated[str, Field(description=arg_description)],
                )
                for arg_name, arg_description in command_config.args.items()
            ]
        )

        # Set the function annotations to match the signature.
        _tool_function.__annotations__ = {
            **{
                arg_name: Annotated[str, Field(description=arg_description)]
                for arg_name, arg_description in command_config.args.items()
            },
            "return": str,
        }

        return _tool_function
