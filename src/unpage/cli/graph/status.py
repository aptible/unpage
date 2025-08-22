import sys

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
        print("No graph build running")
        sys.exit(1)

    try:
        pid = int(pid_file.read_text().strip())
        if is_process_running(pid):
            print(f"Graph build running (PID: {pid})")

            # Show log file info if it exists
            log_file = get_log_file()
            if log_file.exists():
                print("View logs: unpage graph logs --follow")
        else:
            cleanup_pid_file()
            print("No graph build running")
            sys.exit(1)
    except ValueError:
        cleanup_pid_file()
        print("No graph build running")
        sys.exit(1)
