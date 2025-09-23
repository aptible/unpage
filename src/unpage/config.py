"""Configuration management for unpage CLI."""

import shutil
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Self

import yaml
from expandvars import expandvars
from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings


def yaml_to_model[T: BaseModel](
    model_class: type[T],
    yaml_content: str | Path,
    **overrides: Any,
) -> T:
    """Load YAML content into a Pydantic model with optional field overrides.

    Args:
        model_class: The Pydantic model class to create
        yaml_content: YAML content as string or Path to YAML file
        **overrides: Additional keyword arguments to override/merge with YAML values

    Returns:
        Instance of the model class with data from YAML and overrides

    Raises:
        FileNotFoundError: If yaml_content is a Path that doesn't exist
        yaml.YAMLError: If YAML content is invalid
        pydantic.ValidationError: If the resulting data doesn't match the model
    """
    # Load YAML content
    content = yaml_content.read_text() if isinstance(yaml_content, Path) else yaml_content

    # Parse YAML
    yaml_data = yaml.safe_load(content) or {} if content.strip() else {}

    # Ensure data is a dictionary
    if not isinstance(yaml_data, dict):
        raise ValueError(f"YAML content must be a dictionary, got {type(yaml_data).__name__}")

    # Create and return model instance
    return model_class(
        **{
            **yaml_data,
            # Merge overrides into data (overrides take precedence)
            **overrides,
        }
    )


class Environment(BaseSettings):
    """Environment variables for unpage configuration."""

    UNPAGE_CONFIG_ROOT: Path | None = None

    def get_config_root(self) -> Path:
        """Get the configuration directory, with fallback to default."""
        return self.UNPAGE_CONFIG_ROOT or (Path.home() / ".unpage")


# Global environment instance
env = Environment()


type PluginSettings = dict[str, Any]
"""type alias to dict[str, Any] that contains settings for the plugin"""


class PluginConfig(BaseModel):
    enabled: bool = True
    settings: PluginSettings = Field(default_factory=dict)

    def __hash__(self) -> int:
        return hash(self.model_dump_json())


class EnvironmentVariablesMixin(BaseModel):
    """Model to recursively expand environment variables in all fields."""

    @model_validator(mode="before")
    @classmethod
    def expand_env_vars(cls, data: Any) -> Any:  # noqa: ANN401
        """Recursively expand environment variables in all string fields."""
        if not isinstance(data, dict):
            return data

        def _expand(value: Any) -> Any:  # noqa: ANN401
            if isinstance(value, str):
                return expandvars(value, nounset=True)
            elif isinstance(value, dict):
                return {k: _expand(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [_expand(item) for item in value]
            else:
                return value

        return _expand(data)


class Config(EnvironmentVariablesMixin, BaseModel):
    """Configuration model for unpage profiles."""

    plugins: dict[str, PluginConfig] = Field(default_factory=dict)
    profile: str = Field(default="default", exclude=True)
    file_path: Path = Field(exclude=True)

    telemetry_enabled: bool = True

    def save(self) -> None:
        """Save this config to its file path."""
        if not self.file_path:
            raise ValueError("Cannot save config: file_path not set")
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with self.file_path.open("w") as f:
            yaml.dump(self.model_dump(), f, default_flow_style=False)

    def merge_plugins(self, other_plugins: dict[str, PluginConfig]) -> Self:
        """Merge another plugins dict into this config's plugins, returning a new Config instance.

        Args:
            other_plugins: Another plugins dict to mergee, may be None in which case self is returned

        Returns:
            Config new instance with merged values
        """
        if not other_plugins:
            return self

        return self.__class__(
            **{
                "file_path": self.file_path,
                "profile": self.profile,
                **self.model_dump(),
                "plugins": {**self.plugins, **other_plugins},
            }
        )


class ConfigManager:
    """Manages user configuration and profiles for unpage."""

    def __init__(self, config_root: Path | None = None) -> None:
        """Initialize configuration manager.

        Args:
            config_root: Custom config directory. Defaults to UNPAGE_CONFIG_ROOT or ~/.unpage
        """
        self.config_root = config_root or env.get_config_root()
        self.profiles_dir = self.config_root / "profiles"
        self.active_profile_file = self.config_root / ".profile"
        self.active_profile_override = None
        self._ensure_config_structure()

    def _ensure_config_structure(self) -> None:
        """Ensure the configuration directory structure exists."""
        self.config_root.mkdir(exist_ok=True)
        self.profiles_dir.mkdir(exist_ok=True)

        # Create default profile if it doesn't exist
        default_profile = self.profiles_dir / "default"
        if not default_profile.exists():
            self.create_profile("default")

        # Set default profile as current if no profile is set
        if not self.active_profile_file.exists():
            self.set_active_profile("default")

    def get_empty_config(self, profile: str, **overrides: Any) -> Config:
        """Get an empty config object."""
        # Need to import here to avoid circular import
        from unpage.plugins.base import REGISTRY

        return Config(
            profile=profile,
            file_path=self.profiles_dir / profile / "config.yaml",
            **{
                "plugins": {
                    p: PluginConfig(enabled=True, settings=plugin_cls.default_plugin_settings)
                    for p, plugin_cls in REGISTRY.items()
                },
                **overrides,
            },
        )

    def create_profile(self, name: str) -> Path:
        """Create a new profile with an empty config.yaml.

        Args:
            name: Name of the profile to create

        Returns:
            Path to the created profile directory

        Raises:
            FileExistsError: If profile already exists
        """
        profile_dir = self.profiles_dir / name

        if profile_dir.exists():
            raise FileExistsError(f"Profile {name!r} already exists")

        profile_dir.mkdir(parents=True, exist_ok=True)

        # Create empty config file using Config model
        empty_config = Config(profile=name, file_path=profile_dir / "config.yaml")
        empty_config.save()

        return profile_dir

    def list_profiles(self) -> list[str]:
        """List all available profiles.

        Returns:
            List of profile names
        """
        if not self.profiles_dir.exists():
            return []

        return [
            p.name
            for p in self.profiles_dir.iterdir()
            if p.is_dir() and (p / "config.yaml").exists()
        ]

    def get_profile_directory(self, name: str) -> Path:
        """Get the directory for a specific profile.

        Args:
            name: Profile name

        Returns:
            Path to the profile directory
        """
        return self.profiles_dir / name

    def get_profile_config(self, name: str) -> Config:
        """Get configuration for a specific profile.

        Args:
            name: Profile name

        Returns:
            Configuration object

        Raises:
            FileNotFoundError: If profile doesn't exist
        """
        profile_dir = self.profiles_dir / name
        config_file = profile_dir / "config.yaml"

        if not config_file.exists():
            raise FileNotFoundError(f"Profile {name!r} not found")

        # Load config from YAML file with overrides
        return yaml_to_model(Config, config_file, profile=name, file_path=config_file)

    def get_active_profile(self) -> str:
        """Get the name of the currently active profile.

        Returns:
            Name of active profile
        """
        if self.active_profile_override:
            return self.active_profile_override

        if not self.active_profile_file.exists():
            return "default"

        return self.active_profile_file.read_text().strip()

    def set_active_profile(self, name: str) -> None:
        """Set the current active profile.

        Args:
            name: Profile name to set as active

        Raises:
            FileNotFoundError: If profile doesn't exist
        """
        profile_dir = self.profiles_dir / name
        if not profile_dir.exists():
            raise FileNotFoundError(f"Profile {name!r} not found")

        self.active_profile_file.write_text(name)

    @contextmanager
    def active_profile(self, name: str) -> Generator[None, None, None]:
        """Context manager for setting the active profile."""
        self.active_profile_override = name
        try:
            yield
        finally:
            self.active_profile_override = None

    def get_active_profile_directory(self) -> Path:
        """Get the directory for the currently active profile.

        Returns:
            Path to the active profile directory
        """
        active_profile = self.get_active_profile()
        return self.get_profile_directory(active_profile)

    def get_active_profile_config(self) -> Config:
        """Get configuration for the currently active profile.

        Returns:
            Configuration object for the active profile
        """
        active_profile = self.get_active_profile()
        return self.get_profile_config(active_profile)

    def delete_profile(self, name: str) -> None:
        """Delete a profile.

        Args:
            name: Profile name to delete
        """
        profile_dir = self.profiles_dir / name
        if not profile_dir.exists():
            raise FileNotFoundError(f"Profile {name!r} not found")

        shutil.rmtree(profile_dir)


# Global config manager instance
manager = ConfigManager()
