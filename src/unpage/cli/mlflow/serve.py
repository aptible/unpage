import asyncio
import shlex
from typing import Annotated

from rich import print

from unpage.cli.mlflow._app import mlflow_app
from unpage.cli.options import DEFAULT_PROFILE, ProfileParameter
from unpage.config import manager
from unpage.telemetry import client as telemetry
from unpage.telemetry import prepare_profile_for_telemetry
from unpage.utils import confirm


@mlflow_app.command
async def serve(
    *,
    profile: Annotated[str, ProfileParameter] = DEFAULT_PROFILE,
    port: int = 5566,
) -> None:
    """Start MLflow tracking server

    Parameters
    ----------
    profile
        The profile to use
    port
        Port for MLflow server to listen on
    """
    await telemetry.send_event(
        {
            "command": "mlflow serve",
            **prepare_profile_for_telemetry(profile),
            "port": port,
        }
    )
    host = "127.0.0.1"
    config_dir = manager.get_profile_directory(profile)
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
