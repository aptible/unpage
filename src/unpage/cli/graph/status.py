from typing import Annotated

from unpage.cli.graph._app import graph_app
from unpage.cli.graph._background import (
    cleanup_pid_file,
    get_log_file,
    get_pid_file,
    is_process_running,
)
from unpage.cli.options import DEFAULT_PROFILE, ProfileParameter
from unpage.telemetry import client as telemetry
from unpage.telemetry import prepare_profile_for_telemetry


@graph_app.command
async def status(*, profile: Annotated[str, ProfileParameter] = DEFAULT_PROFILE) -> None:
    """Check if graph build is running

    Parameters
    ----------
    profile
        The profile to use
    """
    await telemetry.send_event(
        {
            "command": "graph status",
            **prepare_profile_for_telemetry(profile),
        }
    )
    
    pid_file = get_pid_file(profile)

    if not pid_file.exists():
        print(f"No graph build running for profile '{profile}'")
        return

    try:
        pid = int(pid_file.read_text().strip())
        if is_process_running(pid):
            print(f"Graph build running for profile '{profile}' (PID: {pid})")

            # Show log file info if it exists
            log_file = get_log_file(profile)
            if log_file.exists():
                print(f"View logs: unpage graph logs --profile {profile} --follow")
        else:
            print(f"Stale PID file found for profile '{profile}', cleaning up...")
            cleanup_pid_file(profile)
    except ValueError:
        print(f"Corrupted PID file found for profile '{profile}', cleaning up...")
        cleanup_pid_file(profile)
