import sys

import rich

from unpage.cli.profile._app import profile_app
from unpage.config import manager


@profile_app.command
def create(profile_name: str) -> None:
    """Create a new profile.

    Parameters
    ----------
    profile_name
        The name of the profile to create
    """
    try:
        manager.create_profile(profile_name)
        rich.print(f"[green]Profile '{profile_name}' created successfully![/green]")
    except FileExistsError:
        rich.print(f"[red]Profile '{profile_name}' already exists![/red]")
        sys.exit(1)
