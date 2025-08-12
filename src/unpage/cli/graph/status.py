from unpage.cli.graph._app import graph_app
from unpage.cli.graph._background import (
    cleanup_pid_file,
    get_log_file,
    get_pid_file,
    is_process_running,
)
from unpage.config import manager
from unpage.telemetry import client as telemetry
from unpage.telemetry import prepare_profile_for_telemetry


@graph_app.command
async def status() -> None:
    """Check if graph build is running"""
    active_profile = manager.get_active_profile()
    await telemetry.send_event(
        {
            "command": "graph status",
            **prepare_profile_for_telemetry(active_profile),
        }
    )

    pid_file = get_pid_file()

    if not pid_file.exists():
        print(f"No graph build running for profile '{active_profile}'")
        return

    try:
        pid = int(pid_file.read_text().strip())
        if is_process_running(pid):
            print(f"Graph build running for profile '{active_profile}' (PID: {pid})")

            # Show log file info if it exists
            log_file = get_log_file()
            if log_file.exists():
                print(f"View logs: unpage graph logs --profile {active_profile} --follow")
        else:
            print(f"Stale PID file found for profile '{active_profile}', cleaning up...")
            cleanup_pid_file()
    except ValueError:
        print(f"Corrupted PID file found for profile '{active_profile}', cleaning up...")
        cleanup_pid_file()
