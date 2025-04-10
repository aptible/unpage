import typer

agent_app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    help="Work with Unpage agents",
)
