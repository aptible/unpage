import colorsys
import importlib
import json
import os
import pkgutil
import re
import shutil
import subprocess
import sys
from collections.abc import Awaitable, Callable, Iterable, Sequence
from pathlib import Path
from re import Pattern
from types import ModuleType
from typing import Any, Generic, TypeVar, cast, overload

import anyio
import questionary
import questionary.constants
import rich
from anyio import create_memory_object_stream
from anyio.abc import TaskGroup
from boltons.iterutils import remap
from pydantic import AnyUrl, ValidationError
from rich.console import Console

T = TypeVar("T")


stderr = Console(stderr=True)


def print(message: str, _indent: int | None = None, **kwargs: Any) -> None:
    stderr.print_json(json.dumps({"message": message, **kwargs}, default=str), indent=_indent)


Choice = questionary.Choice


async def confirm(
    message: str,
    default: bool = True,
    qmark: str = ">",
    style: questionary.Style | None = None,
    auto_enter: bool = False,
    instruction: str | None = None,
    **kwargs: Any,
) -> bool:
    """Convenience wrapper around await questionary.confirm().unsafe_ask_async()"""
    return await questionary.confirm(
        message=message,
        default=default,
        qmark=qmark,
        style=style,
        auto_enter=auto_enter,
        instruction=instruction,
        **kwargs,
    ).unsafe_ask_async()


@overload
async def select(
    message: str,
    choices: Sequence[str],
    default: str | None = None,
    qmark: str = ">",
    pointer: str | None = questionary.constants.DEFAULT_SELECTED_POINTER,
    style: questionary.Style | None = None,
    use_shortcuts: bool = False,
    use_arrow_keys: bool = True,
    use_indicator: bool = False,
    use_jk_keys: bool = True,
    use_emacs_keys: bool = True,
    use_search_filter: bool = False,
    show_selected: bool = False,
    show_description: bool = True,
    instruction: str | None = None,
    **kwargs: Any,
) -> str: ...


@overload
async def select(
    message: str,
    choices: Sequence[questionary.Choice],
    default: questionary.Choice | None = None,
    qmark: str = ">",
    pointer: str | None = questionary.constants.DEFAULT_SELECTED_POINTER,
    style: questionary.Style | None = None,
    use_shortcuts: bool = False,
    use_arrow_keys: bool = True,
    use_indicator: bool = False,
    use_jk_keys: bool = True,
    use_emacs_keys: bool = True,
    use_search_filter: bool = False,
    show_selected: bool = False,
    show_description: bool = True,
    instruction: str | None = None,
    **kwargs: Any,
) -> str: ...


@overload
async def select(
    message: str,
    choices: Sequence[dict[str, Any]],
    default: dict[str, Any] | None = None,
    qmark: str = ">",
    pointer: str | None = questionary.constants.DEFAULT_SELECTED_POINTER,
    style: questionary.Style | None = None,
    use_shortcuts: bool = False,
    use_arrow_keys: bool = True,
    use_indicator: bool = False,
    use_jk_keys: bool = True,
    use_emacs_keys: bool = True,
    use_search_filter: bool = False,
    show_selected: bool = False,
    show_description: bool = True,
    instruction: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]: ...


async def select(
    message: str,
    choices: Sequence[str | questionary.Choice | dict[str, Any]],
    default: str | questionary.Choice | dict[str, Any] | None = None,
    qmark: str = ">",
    pointer: str | None = questionary.constants.DEFAULT_SELECTED_POINTER,
    style: questionary.Style | None = None,
    use_shortcuts: bool = False,
    use_arrow_keys: bool = True,
    use_indicator: bool = False,
    use_jk_keys: bool = True,
    use_emacs_keys: bool = True,
    use_search_filter: bool = False,
    show_selected: bool = False,
    show_description: bool = True,
    instruction: str | None = None,
    **kwargs: Any,
) -> str | questionary.Choice | dict[str, Any]:
    """Convenience wrapper around await questionary.select().unsafe_ask_async()"""
    return await questionary.select(
        message=message,
        choices=choices,
        default=default,
        qmark=qmark,
        pointer=pointer,
        style=style,
        use_shortcuts=use_shortcuts,
        use_arrow_keys=use_arrow_keys,
        use_indicator=use_indicator,
        use_jk_keys=use_jk_keys,
        use_emacs_keys=use_emacs_keys,
        use_search_filter=use_search_filter,
        show_selected=show_selected,
        show_description=show_description,
        instruction=instruction,
        **kwargs,
    ).unsafe_ask_async()


@overload
async def checkbox(
    message: str,
    choices: Sequence[str],
    default: str | None = None,
    validate: Callable[[list[str]], bool | str] = lambda a: True,
    qmark: str = ">",
    pointer: str | None = questionary.constants.DEFAULT_SELECTED_POINTER,
    style: questionary.Style | None = None,
    initial_choice: str | None = None,
    use_arrow_keys: bool = True,
    use_jk_keys: bool = True,
    use_emacs_keys: bool = True,
    use_search_filter: str | bool | None = False,
    instruction: str | None = None,
    show_description: bool = True,
    **kwargs: Any,
) -> Sequence[str]: ...


@overload
async def checkbox(
    message: str,
    choices: Sequence[questionary.Choice],
    default: str | None = None,
    validate: Callable[[list[str]], bool | str] = lambda a: True,
    qmark: str = ">",
    pointer: str | None = questionary.constants.DEFAULT_SELECTED_POINTER,
    style: questionary.Style | None = None,
    initial_choice: questionary.Choice | None = None,
    use_arrow_keys: bool = True,
    use_jk_keys: bool = True,
    use_emacs_keys: bool = True,
    use_search_filter: str | bool | None = False,
    instruction: str | None = None,
    show_description: bool = True,
    **kwargs: Any,
) -> Sequence[questionary.Choice]: ...


@overload
async def checkbox(
    message: str,
    choices: Sequence[dict[str, Any]],
    default: str | None = None,
    validate: Callable[[list[str]], bool | str] = lambda a: True,
    qmark: str = ">",
    pointer: str | None = questionary.constants.DEFAULT_SELECTED_POINTER,
    style: questionary.Style | None = None,
    initial_choice: dict[str, Any] | None = None,
    use_arrow_keys: bool = True,
    use_jk_keys: bool = True,
    use_emacs_keys: bool = True,
    use_search_filter: str | bool | None = False,
    instruction: str | None = None,
    show_description: bool = True,
    **kwargs: Any,
) -> Sequence[dict[str, Any]]: ...


async def checkbox(
    message: str,
    choices: Sequence[str | questionary.Choice | dict[str, Any]],
    default: str | None = None,
    validate: Callable[[list[str]], bool | str] = lambda a: True,
    qmark: str = ">",
    pointer: str | None = questionary.constants.DEFAULT_SELECTED_POINTER,
    style: questionary.Style | None = None,
    initial_choice: str | questionary.Choice | dict[str, Any] | None = None,
    use_arrow_keys: bool = True,
    use_jk_keys: bool = True,
    use_emacs_keys: bool = True,
    use_search_filter: str | bool | None = False,
    instruction: str | None = None,
    show_description: bool = True,
    **kwargs: Any,
) -> Sequence[str | questionary.Choice | dict[str, Any]]:
    return await questionary.checkbox(
        message=message,
        choices=choices,
        default=default,
        validate=validate,
        qmark=qmark,
        pointer=pointer,
        style=style,
        initial_choice=initial_choice,
        use_arrow_keys=use_arrow_keys,
        use_jk_keys=use_jk_keys,
        use_emacs_keys=use_emacs_keys,
        use_search_filter=use_search_filter,
        instruction=instruction,
        show_description=show_description,
        **kwargs,
    ).unsafe_ask_async()


def import_submodules(
    package: str | ModuleType,
    recursive: bool = True,
) -> dict[str, ModuleType]:
    """Import all submodules of a module, recursively, including subpackages

    :param package: package (name or actual module)
    :type package: str | module
    :rtype: dict[str, types.ModuleType]
    """
    if isinstance(package, str):
        package = importlib.import_module(package)
    results: dict[str, ModuleType] = {}
    for _, name, is_pkg in pkgutil.walk_packages(package.__path__):
        full_name = f"{package.__name__}.{name}"
        try:
            results[full_name] = importlib.import_module(full_name)
        except ModuleNotFoundError:
            continue
        if recursive and is_pkg:
            results.update(import_submodules(full_name))
    return results


class classproperty(Generic[T]):
    """
    Decorator that converts a method with a single cls argument into a property
    that can be accessed directly from the class.
    """

    def __init__(self, method: Callable[[Any], T]) -> None:
        self.fget = method

    def __get__(self, instance: object, cls: type | None = None) -> T:
        return self.fget(cls if cls else instance.__class__)

    def getter(self, method: Callable[[Any], T]) -> "classproperty[T]":
        self.fget = method
        return self


def as_completed(tg: TaskGroup, aws: Iterable[Awaitable[T]]) -> Iterable[Awaitable[T]]:
    send_stream, receive_stream = create_memory_object_stream[T | Exception]()

    # Convert the iterable to a list to get its length
    aws_list = list(aws)
    count = len(aws_list)
    completed = 0

    async def populate_result(a: Awaitable[T]) -> None:
        nonlocal completed
        try:
            result = await a
            await send_stream.send(result)
        except Exception as e:
            # Send the exception too, so it can be raised in the caller's context
            await send_stream.send(e)
        finally:
            completed += 1
            # Close the send stream when all tasks are done
            if completed >= count:
                await send_stream.aclose()

    async def wait_for_result() -> T:
        try:
            result = await receive_stream.receive()
            # If we received an exception, raise it
            if isinstance(result, Exception):
                raise result
            return result
        except anyio.EndOfStream as e:
            # This should only happen if all senders are done but we're still trying to receive
            raise StopIteration("No more results available") from e

    for a in aws_list:
        tg.start_soon(populate_result, a)

    return (wait_for_result() for _ in aws_list)


def generate_contrasting_colors(n: int) -> list[tuple[str, str]]:
    """
    Generate N visually distinct colors as (background, foreground) hex pairs.

    The background colors are chosen by evenly spacing hues around the HSL color wheel.
    The foreground color is either black or white, chosen for maximum contrast.

    Args:
        n (int): Number of color pairs to generate.

    Returns:
        List[Tuple[str, str]]: List of (background_hex, foreground_hex) tuples.
    """

    def luminance(r: float, g: float, b: float) -> float:
        # sRGB to linear RGB conversion
        def to_linear(c: float) -> float:
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

        r_lin, g_lin, b_lin = map(to_linear, (r, g, b))
        return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin

    def get_foreground_color(r: float, g: float, b: float) -> str:
        return "#000000" if luminance(r, g, b) > 0.5 else "#ffffff"

    color_pairs: list[tuple[str, str]] = []
    for i in range(n):
        hue = i / n
        saturation = 0.65
        lightness = 0.5
        r, g, b = colorsys.hls_to_rgb(hue, lightness, saturation)
        hex_color = f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"
        fg_color = get_foreground_color(r, g, b)
        color_pairs.append((hex_color, fg_color))

    return color_pairs


def camel_to_snake(s: str) -> str:
    """Convert a camelCase string to a snake_case string."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", s).lower()


def strip_secrets(data: dict[str, Any]) -> dict[str, Any]:
    """Strip secrets from a dictionary."""

    # Define a constant for redacted content
    REDACTED = "REDACTED"

    def _visit(_path: tuple[str, ...], key: str, value: Any) -> bool | tuple[str, Any]:  # noqa: ANN401
        if key in ("passphrase", "connection_url"):
            return False
        if key == "env" and isinstance(value, dict):
            value = cast("dict[str, Any]", value)
            clean_env: dict[str, Any] = {}
            for k, v in value.items():
                clean_env[k] = v

                # If it's a URL, redact the password
                try:
                    original_url = AnyUrl(v)
                except ValidationError:
                    pass
                else:
                    if not original_url.host:
                        clean_env[k] = str(original_url)
                        continue
                    else:
                        clean_env[k] = str(
                            AnyUrl.build(
                                scheme=original_url.scheme,
                                username=original_url.username,
                                password=REDACTED,
                                host=original_url.host,
                                port=original_url.port,
                                path=original_url.path,
                                query=original_url.query,
                                fragment=original_url.fragment,
                            )
                        )

                if any(
                    secret_indicator in k.upper()
                    for secret_indicator in (
                        "KEY",
                        "PASS",
                        "PASSPHRASE",
                        "PASSWORD",
                        "PSK",
                        "SECRET",
                        "TOKEN",
                    )
                ):
                    clean_env[k] = REDACTED
            return "env", clean_env
        return True

    return remap(data, _visit)


def compile_regex(pattern: str) -> Pattern[str]:
    """Compile a string into a regex pattern."""
    # Extract the pattern and flags from the string
    delimiter = pattern[0]
    if pattern.rfind(delimiter) == 0:
        raise ValueError("Invalid regex pattern: Missing closing delimiter")

    # Split the pattern and the flags
    parts = pattern.rsplit(delimiter, 1)
    raw_pattern = parts[0][1:]
    flags_str = parts[1] if len(parts) > 1 else ""

    # Map string flags to re module flags
    flag_map = {
        "g": 0,  # Global flag is not needed in Python regex
        "i": re.IGNORECASE,
        "m": re.MULTILINE,
        "s": re.DOTALL,
        "x": re.VERBOSE,
        "u": re.UNICODE,
    }

    # Calculate the combined flags
    flags = 0
    for char in flags_str:
        if char in flag_map:
            flags |= flag_map[char]
        else:
            raise ValueError(f"Unknown regex flag: {char}")

    # Compile the regex pattern with the calculated flags
    return re.compile(raw_pattern, flags)


def wildcard_or_regex_match(pattern: str, string: str) -> bool:
    """Match a string against a wildcard or regex pattern.

    - If pattern is surrounded by slashes (/regex/), treat it as a raw regular expression.
    - Otherwise, treat '*' as a wildcard matching any sequence of characters.
    """
    if pattern.startswith("/") and pattern.endswith("/") and len(pattern) > 1:
        # Regex mode
        regex = pattern[1:-1]  # Strip the surrounding slashes
    else:
        # Wildcard mode: escape and convert '*' to '.*'
        escaped = re.escape(pattern)
        regex = "^" + escaped.replace(r"\*", ".*") + "$"

    return re.match(regex, string) is not None


def wildcard_or_regex_match_any(patterns: list[str], string: str) -> bool:
    """Match a string against any of the given wildcard or regex patterns."""
    return any(wildcard_or_regex_match(pattern, string) for pattern in patterns)


async def edit_file(file_path: str | Path, editor: str | None = None) -> None:
    """Edit a file in the user's editor."""
    editor = editor or get_editor()
    if not editor:
        raise ValueError("No editor specified")

    # Split editor command into command and arguments
    editor_cmd, *editor_args = shlex.split(editor)

    # Check if the editor command exists in PATH
    editor_path = shutil.which(editor_cmd)
    if not editor_path:
        rich.print(f"[red]Editor '{editor_cmd}' not found in $PATH[/red]")
        rich.print(f"[blue]Please manually open: {str(file_path)!r}[/blue]")
        return

    try:
        # Combine editor path, args, and file path into the command
        command = [editor_path, *editor_args, str(file_path)]
        await anyio.run_process(
            command,
            # Set the standard streams so that the editor process can properly interact with the terminal.
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
    except subprocess.CalledProcessError:
        rich.print(f"[red]Failed to open {str(file_path)!r} with {editor!r}[/red]")
        rich.print(f"[blue]Please manually open: {str(file_path)!r}[/blue]")
    except FileNotFoundError:
        rich.print(f"[red]Editor '{editor_cmd}' not found[/red]")
        rich.print(f"[blue]Please manually open: {str(file_path)!r}[/blue]")


def get_editor() -> str | None:
    return os.environ.get("DAYDREAM_EDITOR") or os.environ.get("EDITOR") or _get_default_editor()


def _get_default_editor() -> str | None:
    if vim := shutil.which("vim"):
        return vim
    if vi := shutil.which("vi"):
        return vi
    if nano := shutil.which("nano"):
        return nano
    if pico := shutil.which("pico"):
        return pico
    if emacs := shutil.which("emacs"):
        return emacs
