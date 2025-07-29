from importlib.metadata import version as get_version
from typing import cast

from dotenv import load_dotenv

from .sentry import *  # noqa: F403
from .vendor import *  # noqa: F403
from .warnings import *  # noqa: F403

__version__ = get_version(cast("str", __package__))

load_dotenv()
