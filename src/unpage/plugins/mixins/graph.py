from unpage.knowledge import Graph
from unpage.plugins import PluginCapability


class KnowledgeGraphMixin(PluginCapability):
    """Capability for plugins that can add nodes and edges to the graph."""

    async def populate_graph(self, graph: Graph) -> None:
        """Initialize the graph with nodes and edges from the plugin."""
        raise NotImplementedError
