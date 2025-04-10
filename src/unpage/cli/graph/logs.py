import shutil
import subprocess

import typer

from unpage.cli.graph._app import graph_app
from unpage.cli.graph._background import get_log_file
from unpage.cli.options import PROFILE_OPTION


@graph_app.command()
def logs(
    profile: str = PROFILE_OPTION,
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
) -> None:
    """View graph build logs"""
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
            subprocess.run([tail_cmd, "-f", str(log_file)])
        except KeyboardInterrupt:
            print("\nStopped following logs")
    else:
        print(f"Recent logs for profile '{profile}':")
        print(f"Log file: {log_file}")

        result = subprocess.run(
            [tail_cmd, "-n", "50", str(log_file)], capture_output=True, text=True
        )
        print(result.stdout)
