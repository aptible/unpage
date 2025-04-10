from pathlib import Path
from typing import Any

import typer
import yaml
from pydantic import BaseModel, Field
from pydantic_yaml import to_yaml_str

CONFIG_ROOT = Path(typer.get_app_dir("unpage", force_posix=True))
DEFAULT_CONFIG_FILE = Path(__file__).parent / "defaults.yaml"


type PluginSettings = dict[str, Any]
"""type alias to dict[str, Any] that contains settings for the plugin"""


class PluginConfig(BaseModel):
    enabled: bool = True
    settings: PluginSettings = Field(default_factory=dict)

    def __hash__(self) -> int:
        return hash(self.model_dump_json())


class Config(BaseModel):
    plugins: dict[str, PluginConfig] = {}


DEFAULT_CONFIG = Config(
    **yaml.safe_load(DEFAULT_CONFIG_FILE.read_text()),
)


def get_config_dir(profile: str, create: bool = False) -> Path:
    config_dir = CONFIG_ROOT / "profiles" / profile

    # Create a new config directory if it doesn't exist.
    if not config_dir.exists():
        if not create:
            raise FileNotFoundError(f"Config directory {config_dir} does not exist")
        config_dir.mkdir(parents=True, exist_ok=True)

    return config_dir


def get_config_path(profile: str, create: bool = False) -> Path:
    return get_config_dir(profile, create) / "config.yaml"


def load_config(profile: str, create: bool = False) -> Config:
    config_path = get_config_path(profile, create)

    # Create a new config file if it doesn't exist.
    if not config_path.exists():
        if not create:
            raise FileNotFoundError(f"Config file {config_path} does not exist")
        config_path.write_text(DEFAULT_CONFIG_FILE.read_text())

    # Merge the default config with the user config, with the user config taking precedence.
    return Config(**{**DEFAULT_CONFIG.model_dump(), **yaml.safe_load(config_path.read_text())})


def save_config(cfg: Config, profile: str, create: bool = False) -> None:
    config_path = get_config_path(profile, create)
    yaml_str = to_yaml_str(cfg, default_flow_style=False)
    config_path.write_text(yaml_str, encoding="utf-8")
