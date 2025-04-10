import os
import signal

from unpage.cli.graph._app import graph_app
from unpage.cli.graph._background import cleanup_pid_file, get_pid_file, is_process_running
from unpage.cli.options import PROFILE_OPTION


@graph_app.command()
def stop(profile: str = PROFILE_OPTION) -> None:
    """Stop running graph build"""
    pid_file = get_pid_file(profile)

    if not pid_file.exists():
        print(f"No graph build running for profile '{profile}'")
        return

    try:
        pid = int(pid_file.read_text().strip())
        if is_process_running(pid):
            print(f"Stopping graph build for profile '{profile}' (PID: {pid})...")
            os.kill(pid, signal.SIGTERM)
            print("Graph build stopped successfully")
        else:
            print(f"Process not found for profile '{profile}', cleaning up stale PID file...")
        cleanup_pid_file(profile)
    except (ValueError, ProcessLookupError):
        cleanup_pid_file(profile)
        print(f"No running process found for profile '{profile}', cleaned up stale PID file")
