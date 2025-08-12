import rich

from unpage.cli.profile._app import profile_app
from unpage.config import manager
from unpage.utils import confirm


@profile_app.command
async def delete(profile_name: str, *, force: bool = False) -> None:
    """Delete a profile.

    Parameters
    ----------
    profile_name
        The name of the profile to delete
    force
        Force deletion even if it's the active profile
    """
    # Check if profile exists first
    available_profiles = manager.list_profiles()
    if profile_name not in available_profiles:
        rich.print(f"[red]Profile '{profile_name}' does not exist[/red]")
        rich.print(f"Available profiles: {', '.join(available_profiles)}")
        return

    # Prevent deleting the default profile
    if profile_name == "default":
        rich.print("[red]Cannot delete the default profile[/red]")
        return

    # Check if the profile is the active profile
    active_profile = manager.get_active_profile()
    if profile_name == active_profile and not force:
        rich.print(
            f"[red]Cannot delete active profile '{profile_name}'. Use --force or switch to a different profile first.[/red]"
        )
        return

    # Confirm deletion unless forced
    if not force:
        confirmed = await confirm(f"Are you sure you want to delete profile '{profile_name}'?")
        if not confirmed:
            rich.print("Deletion cancelled.")
            return

    # Attempt to delete the profile
    manager.delete_profile(profile_name)
    rich.print(f"[green]Profile '{profile_name}' deleted successfully[/green]")

    # If we deleted the active profile, inform user of the switch
    if profile_name == active_profile:
        # Switch to the first profile
        manager.set_active_profile("default")
        rich.print(f"[yellow]Switched to profile '{manager.get_active_profile()}'[/yellow]")
