import sys

import rich

from unpage.cli.profile._app import profile_app
from unpage.config import manager


@profile_app.command
def use(profile_name: str) -> None:
    """Set the active profile.

    Parameters
    ----------
    profile_name
        The name of the profile to use
    """
    # Check if profile exists first
    available_profiles = manager.list_profiles()
    if profile_name not in available_profiles:
        rich.print(f"[red]Profile '{profile_name}' does not exist![/red]")
        rich.print(f"Available profiles: {', '.join(available_profiles)}")
        sys.exit(1)

    manager.set_active_profile(profile_name)
    rich.print(f"[green]Switched to profile '{profile_name}'[/green]")
