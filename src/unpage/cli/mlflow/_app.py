import typer

mlflow_app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    help="Debug with MLflow",
)
