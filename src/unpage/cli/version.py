import inspect

import rich

from unpage.cli._app import app
from unpage.telemetry import client as telemetry


@app.command
async def version(*, json: bool = False) -> None:
    """Display the version of the Unpage CLI.

    Parameters
    ----------
    json
        Return the version information as JSON
    """
    await telemetry.send_event(
        {
            "command": "version",
            "json_output": json,
        }
    )

    from dspy import __version__ as dspy_version
    from dspy.adapters.types.tool import Tool

    from unpage import __version__

    dspy_parse_function_tool_source = inspect.getsource(Tool._parse_function)
    dspy_tool_no_input_args_bugfix_present = all(
        " is not None else " in line for line in dspy_parse_function_tool_source.splitlines()[-3:-1]
    )

    if json:
        rich.print_json(
            data={
                "unpage": __version__,
                "dspy": dspy_version,
                "dspy_tool_no_input_args_bugfix_present": dspy_tool_no_input_args_bugfix_present,
            }
        )
        return
    print(f"unpage {__version__} (dspy {dspy_version} {dspy_tool_no_input_args_bugfix_present=})")
