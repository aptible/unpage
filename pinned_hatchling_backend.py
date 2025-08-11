"""This module is a custom build backend that wraps `hatching.build`.

It patches the `pyproject.toml` file with pinned dependencies from `uv.lock`
before building the wheel or sdist.
"""

import functools
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import tomlkit
from hatchling import build

PROJECT_ROOT = Path(__file__).parent


def _get_pinned_dependencies() -> list[str]:
    """Get pinned dependencies from uv.lock"""
    uv = shutil.which("uv")

    if uv is None:
        raise FileNotFoundError("uv command not found. Please install uv first.")

    result = subprocess.run(
        [
            uv,
            "export",
            "--format=requirements-txt",
            "--no-header",
            "--no-hashes",
            "--no-editable",
            "--no-dev",
            "--no-annotate",
            "--no-emit-project",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    return result.stdout.strip().splitlines()


def _with_pinned_dependencies(func: Callable) -> Callable:
    """Decorator that temporarily patches pyproject.toml with pinned dependencies"""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        pyproject_path = Path("pyproject.toml")
        backup_path = Path("pyproject.toml.backup")

        # Read current config
        config = tomlkit.loads(pyproject_path.read_text())

        # Backup original
        shutil.copy2(pyproject_path, backup_path)

        try:
            # Update with pinned dependencies
            project = cast("dict[str, Any]", config["project"])
            project["dependencies"] = _get_pinned_dependencies()
            config["project"] = project

            # Write modified version
            pyproject_path.write_text(tomlkit.dumps(config))

            # Call the original function
            return func(*args, **kwargs)

        finally:
            # Restore original pyproject.toml
            if backup_path.exists():
                shutil.move(backup_path, "pyproject.toml")

    return wrapper


# Functions that trigger actual builds and need dependency pinning
BUILD_FUNCTIONS = {"build_wheel", "build_sdist"}


def __getattr__(name: str) -> Any:  # noqa: ANN401
    """Dynamically proxy all attributes from `hatchling.build`.

    Wraps build functions with dependency pinning and passes through all other
    calls unchanged.
    """
    if not hasattr(build, name):
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

    attr = getattr(build, name)

    # If it's a build function, wrap it with dependency pinning
    if name in BUILD_FUNCTIONS and callable(attr):
        return _with_pinned_dependencies(attr)

    # Otherwise, pass through unchanged
    return attr
