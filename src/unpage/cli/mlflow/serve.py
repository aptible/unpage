import asyncio
import shlex

import anyio
import typer
from rich import print

from unpage.cli.mlflow._app import mlflow_app
from unpage.cli.options import PROFILE_OPTION
from unpage.config.utils import get_config_dir
from unpage.utils import confirm


@mlflow_app.command()
def serve(
    profile: str = PROFILE_OPTION,
    port: int = typer.Option(default=5566, help="Port for MLflow server to listen on"),
) -> None:
    async def _server() -> None:
        host = "127.0.0.1"
        config_dir = get_config_dir(profile, create=True)
        mlflow_db = config_dir / "mlflow" / "debug.db"
        mlflow_db.parent.mkdir(parents=True, exist_ok=True)
        mlflow_db.unlink(missing_ok=True)
        backend_store_uri = f"sqlite:///{mlflow_db.absolute()}"
        artifacts_dir = mlflow_db.parent / "mlartifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        cmd = (
            "uvx mlflow@3 server "
            f"--host {shlex.quote(host)} --port {shlex.quote(str(port))} "
            f"--backend-store-uri {shlex.quote(backend_store_uri)} "
            f"--artifacts-destination {shlex.quote(str(artifacts_dir.absolute()))}"
        )
        print(
            f"MLflow tracking server is ready to start! Set this in your environment to use it: MLFLOW_TRACKING_URI=http://{host}:{port}"
        )
        while not await confirm("Ready to start MLflow tracking server?"):
            pass
        print(f"  ...running: {cmd}")
        proc = await asyncio.create_subprocess_shell(cmd)
        await proc.wait()

    anyio.run(_server)
