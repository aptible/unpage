import asyncio
import shutil

import anyio
import typer

from unpage.cli.graph._app import graph_app
from unpage.cli.graph._background import get_log_file
from unpage.cli.options import PROFILE_OPTION
from unpage.telemetry import client as telemetry
from unpage.telemetry import prepare_profile_for_telemetry


@graph_app.command()
def logs(
    profile: str = PROFILE_OPTION,
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
) -> None:
    """View graph build logs"""

    async def _run() -> None:
        await telemetry.send_event(
            {
                "command": "graph logs",
                **prepare_profile_for_telemetry(profile),
                "follow": follow,
            }
        )
        log_file = get_log_file(profile)
        tail_cmd = shutil.which("tail")
        if not tail_cmd:
            print("'tail' command not found. Please install it.")
            return

        if not log_file.exists():
            print(f"No log file found for profile '{profile}'")
            print(f"Expected location: {log_file}")
            return

        if follow:
            print(f"Following logs for profile '{profile}' (Ctrl+C to stop)")
            print(f"Log file: {log_file}")

            try:
                proc = await asyncio.create_subprocess_shell(f"{tail_cmd} -f {log_file!s}")
                await proc.wait()
            except KeyboardInterrupt:
                print("\nStopped following logs")
        else:
            print(f"Recent logs for profile '{profile}':")
            print(f"Log file: {log_file}")

            proc = await asyncio.create_subprocess_shell(f"{tail_cmd} -n 50 {log_file!s}")
            await proc.wait()

    anyio.run(_run)
