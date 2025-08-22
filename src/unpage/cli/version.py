import rich

from unpage import __version__
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

    if json:
        rich.print_json(
            data={
                "unpage": __version__,
            }
        )
        return
    print(f"unpage {__version__}")
