import inspect

import rich
import typer

from unpage.cli._app import app


@app.command()
def version(json: bool = typer.Option(False, help="return json output")) -> None:
    """
    Display the version of the Unpage CLI.
    """
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
