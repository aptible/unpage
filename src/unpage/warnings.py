import os
import sys
import traceback
import warnings
from typing import TextIO


def warn_with_traceback(
    message: str,
    category: type[Warning],
    filename: str,
    lineno: int,
    file: TextIO | None = None,
    line: str | None = None,
) -> None:
    log = file if file and hasattr(file, "write") else sys.stderr
    traceback.print_stack(file=log)
    log.write(warnings.formatwarning(message, category, filename, lineno, line))


# Render warnings with traceback to make it easier to track down the culprit.
if os.getenv("WARN_WITH_TRACEBACK", "false").lower() == "true":
    warnings.showwarning = warn_with_traceback


def filter_all_warnings() -> None:
    if not any(
        os.getenv("UNPAGE_DEVELOPER", "false").lower().startswith(x) for x in ("1", "t", "y")
    ):
        warnings.filterwarnings("ignore")
