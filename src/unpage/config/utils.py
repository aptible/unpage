from pathlib import Path

import typer
import yaml
from pydantic_yaml import to_yaml_str

from unpage.config.manager import Config, manager

CONFIG_ROOT = Path(typer.get_app_dir("unpage", force_posix=True))
DEFAULT_CONFIG_FILE = Path(__file__).parent / "defaults.yaml"


DEFAULT_CONFIG = Config(
    **yaml.safe_load(DEFAULT_CONFIG_FILE.read_text()),
)


def get_config_path(profile: str, create: bool = False) -> Path:
    return manager.get_profile_directory(profile) / "config.yaml"


def get_global_config_path() -> Path:
    return CONFIG_ROOT / "config.yaml"


def load_global_config() -> Config:
    global_config_path = get_global_config_path()

    if not global_config_path.exists():
        return Config()

    try:
        return Config(**yaml.safe_load(global_config_path.read_text()))
    except Exception:
        return Config()


def load_config(profile: str, create: bool = False) -> Config:
    return manager.get_profile_config(profile)


def save_config(cfg: Config, profile: str, create: bool = False) -> None:
    config_path = get_config_path(profile, create)
    yaml_str = to_yaml_str(cfg, default_flow_style=False)
    config_path.write_text(yaml_str, encoding="utf-8")
