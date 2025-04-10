import typer

DEFAULT_PROFILE = "default"
PROFILE_OPTION = typer.Option(
    ...,
    "--profile",
    envvar="UNPAGE_PROFILE",
    help="Use profiles to manage multiple graphs",
    show_default=True,
)
PROFILE_OPTION.default = DEFAULT_PROFILE
