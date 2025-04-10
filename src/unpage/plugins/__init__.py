from unpage.knowledge import Node
from unpage.utils import import_submodules

from .base import REGISTRY, Plugin, PluginCapability, PluginManager

# Autoload all plugins in the plugins directory
import_submodules("unpage.plugins")

__all__ = ["REGISTRY", "Node", "Plugin", "PluginCapability", "PluginManager"]
