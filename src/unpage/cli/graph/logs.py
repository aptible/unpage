import asyncio
import shutil
from typing import Annotated

from unpage.cli.graph._app import graph_app
from unpage.cli.graph._background import get_log_file
from unpage.cli.options import DEFAULT_PROFILE, ProfileParameter
from unpage.telemetry import client as telemetry
from unpage.telemetry import prepare_profile_for_telemetry


@graph_app.command
async def logs(
    *,
    profile: Annotated[str, ProfileParameter] = DEFAULT_PROFILE,
    follow: bool = False,
) -> None:
    """View graph build logs

    Parameters
    ----------
    profile
        The profile to use
    follow
        Follow log output
    """
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
