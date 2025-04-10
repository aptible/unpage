import re
from typing import Any

import networkx as nx

from unpage.knowledge import Graph
from unpage.plugins.base import Plugin
from unpage.plugins.mixins import McpServerMixin, tool
from unpage.utils import compile_regex


class GraphPlugin(Plugin, McpServerMixin):
    @property
    def graph(self) -> Graph:
        return self.context.graph

    @tool()
    async def search_resources(self, identifier_or_regex: str) -> list[str] | str:
        """Find resources with an identifier matching the given identifier or
        regular expression.

        To use a regular expression, surround it with slashes. For example,
        `/^my-resource-\\d+$/` will match any resource that starts with
        `my-resource-` and is followed by one or more digits.

        Returns the node IDs, which can be used with get_resource_details to
        get the full resource.
        """
        is_regex = re.match(r"^/.*/[gimsxu]*$", identifier_or_regex) is not None

        # Compile the pattern if it's a regex (or turn the string into an exact-match regex)
        pattern = compile_regex(
            identifier_or_regex if is_regex else rf"/^{re.escape(identifier_or_regex)}$/"
        )

        results = []
        async for node in self.graph.iter_nodes():
            for identifier in (node.nid, *await node.get_identifiers()):
                if not identifier:
                    continue
                if pattern.match(identifier):
                    results.append(node.nid)

        # If there were no results with an exact match, try to fuzzy match any part of identifiers
        if not results and not is_regex:
            fuzzy_pattern = compile_regex(rf"/.*{re.escape(identifier_or_regex)}.*/")
            async for node in self.graph.iter_nodes():
                for identifier in (node.nid, *await node.get_identifiers()):
                    if not identifier:
                        continue
                    if fuzzy_pattern.match(identifier):
                        results.append(node.nid)

        # If there were a lot of results, truncate to 100 and add a message
        if len(results) > 500:
            results = results[:500]
            results.append(
                "Note: There were too many results to return all of them. Consider using other tools to gain a better understanding of the system and refining your search."
            )

        return results or "No resources found matching that identifier."

    @tool()
    async def get_resource_details(self, node_id: str) -> dict[str, Any]:
        """Get the full details of a resource from its node ID."""
        node = await self.graph.get_node(node_id)
        return node.raw_data

    @tool()
    async def get_resource_topology(self) -> str:
        """Get a map of the types of resources and how they're connected.

        You should call this first before trying to search for resources.
        """
        topology = nx.DiGraph()

        async for edge in self.graph.iter_edges():
            source_type = edge.source_node.node_type
            destination_type = edge.destination_node.node_type

            # Add nodes (types) and edge between them
            topology.add_edge(
                source_type,
                destination_type,
                label=edge.properties["relationship_type"],
            )

        return str(nx.nx_pydot.to_pydot(topology))

    @tool()
    async def get_resource_map(
        self,
        root_node_id: str,
        max_depth: int = 2,
    ) -> str:
        """Get a detailed map of a resource and its dependencies.

        This is a good first tool to use when you want to get a high-level
        understanding of some part of the system.

        The root node is the starting point of the map. This tool will return
        all resources directly related to the root resource, and all resources
        related to those resources (etc), up to the given max depth.
        """
        resource_map = nx.DiGraph()

        node = await self.graph.get_node(root_node_id)

        async for edge in self.graph.iter_neighborhood_edges(node, max_depth):
            resource_map.add_edge(
                f'"{edge.source_node.nid}"',
                f'"{edge.destination_node.nid}"',
                label=edge.properties["relationship_type"],
            )

        return str(nx.nx_pydot.to_pydot(resource_map))

    @tool()
    async def get_neighboring_resources(self, node_id: str, max_depth: int = 1) -> list[str]:
        """Get the IDs of the immediate neighbors of the resource with the given node ID.

        Use get_resource_details to get the full details of a resource.
        """
        node = await self.graph.get_node(node_id)
        return [n.nid async for n in self.graph.iter_neighbors(node)]
