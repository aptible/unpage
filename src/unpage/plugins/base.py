from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, Protocol, TypeVar, cast

from unpage.config import Config, PluginConfig, PluginSettings
from unpage.utils import classproperty

if TYPE_CHECKING:
    from unpage.mcp import Context

REGISTRY: dict[str, type["Plugin"]] = {}


class PluginProtocol(Protocol):
    """Protocol for the plugins interface."""

    context: "Context"

    @classproperty
    def name(cls) -> str:  # pyright: ignore[reportRedeclaration]
        """Converts a SomePlugin class to a "some" string, which is the key used in the configuration file.

        For example, AwsPlugin becomes "aws".
        """
        return cast("type[PluginProtocol]", cls).__name__.removesuffix("Plugin").lower()

    name: str


class Plugin(PluginProtocol):
    """Base class for all plugins."""

    def __init__(self, **settings: Any) -> None:
        self._settings = settings

    def __init_subclass__(cls, **kwargs: Any) -> None:
        REGISTRY[cls.name] = cls

    @classproperty
    def default_plugin_settings(cls) -> PluginSettings:
        return {}

    def init_plugin(self) -> None:
        pass

    async def validate_plugin_config(self) -> None:
        """Validate the plugin configuration, ensure authentication works, and anything else that helps ensure the plugin will work when used.

        Plugins should raise an exception if the configuration is invalid or unusable.

        This is called from the `unpage configure` command.
        """
        pass

    async def interactive_configure(self) -> PluginSettings:
        """Interactive wizard for configuring the settings of this plugin. Return final PluginSettings here. Caller is responsible for updating the associated PluginConfig.

        This is called from the `unpage configure` command.
        """
        return {}


class PluginCapability(PluginProtocol):
    """Protocol for capabilities that plugins can have."""


HasPluginCapability = TypeVar("HasPluginCapability", bound=PluginCapability)


class PluginManager:
    """A manager for plugins and their configuration."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._plugins: dict[tuple[str, PluginConfig], Plugin] = {}

    def get_plugin_class(self, name: str) -> type[Plugin]:
        """Return the plugin class for a given name."""
        return REGISTRY[name]

    def get_plugin(self, name: str, config: PluginConfig | None = None) -> Plugin:
        """Return the configured plugin for a given name."""
        config = config or self._config.plugins[name]
        key = (name, config)
        if key not in self._plugins:
            self._plugins[key] = self.get_plugin_class(name)(**config.settings)
            self._plugins[key].init_plugin()
        return self._plugins[key]

    def get_enabled_plugins(self) -> list[Plugin]:
        """Return a list of enabled plugins."""
        enabled_plugins = []
        for name, config in self._config.plugins.items():
            if config.enabled:
                try:
                    enabled_plugins.append(self.get_plugin(name, config))
                except Exception as e:
                    print(f"Error initializing plugin {name!r}: {e}")
                    config.enabled = False
        return enabled_plugins

    def get_plugins_with_capability(
        self,
        capability: type[HasPluginCapability],
    ) -> list[HasPluginCapability]:
        """Return a list of plugins that have the given capability."""
        return [plugin for plugin in self.get_enabled_plugins() if isinstance(plugin, capability)]

    def __iter__(self) -> Iterator[Plugin]:
        """Iterate over all enabled plugins."""
        return iter(self.get_enabled_plugins())
