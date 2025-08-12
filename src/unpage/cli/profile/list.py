import rich

from unpage.cli.profile._app import profile_app
from unpage.config.manager import manager


@profile_app.command(name="list")
def list_profiles() -> None:
    """List all available profiles."""
    profiles = manager.list_profiles()
    active_profile = manager.get_active_profile()

    rich.print("Available profiles:")
    for profile in profiles:
        if profile == active_profile:
            rich.print(f"  [green]* {profile}[/green] (active)")
        else:
            rich.print(f"    {profile}")
