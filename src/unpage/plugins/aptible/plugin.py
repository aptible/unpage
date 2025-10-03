from collections import defaultdict

import anyio
import questionary
import rich

from unpage.config import PluginSettings
from unpage.knowledge import Graph, Node
from unpage.knowledge.edges import Edge
from unpage.plugins import Plugin
from unpage.plugins.aptible.client import AptibleClient
from unpage.plugins.aptible.nodes.base import inflate_resource
from unpage.plugins.mixins import KnowledgeGraphMixin
from unpage.utils import print


class AptiblePlugin(Plugin, KnowledgeGraphMixin):
    """A plugin for the Aptible PaaS."""

    async def interactive_configure(self) -> PluginSettings:
        rich.print("> The Aptible plugin uses your local system authentication.")
        rich.print("> Ensure you are logged into your preferred Aptible organization with:")
        rich.print(">")
        rich.print(">   aptible login")
        rich.print(">")
        rich.print("> Ready to proceed?")
        rich.print("")
        await questionary.press_any_key_to_continue().unsafe_ask_async()
        rich.print("")
        return {}

    async def validate_plugin_config(self) -> None:
        await super().validate_plugin_config()
        async with AptibleClient() as client:
            await client.validate_auth()

    async def populate_graph(self, graph: Graph) -> None:
        """Initialize the graph with nodes and edges from the Aptible API."""
        self.client = AptibleClient()

        edge_count = 0
        seen_nodes = defaultdict(set)

        async with self.client.concurrent_paginator("/edges") as (
            edges,
            total_count,
        ):
            notify_threshold = max(int(total_count * 0.01), 1)

            async for edge in edges:
                source_node = inflate_resource(
                    edge["_embedded"]["source_resource"],
                    _graph=graph,
                )
                destination_node = inflate_resource(
                    edge["_embedded"]["destination_resource"],
                    _graph=graph,
                )

                await graph.add_edge(
                    Edge(
                        source_node=source_node,
                        destination_node=destination_node,
                        properties={
                            "relationship_type": edge["relationship_type"],
                        },
                    )
                )

                if source_node.nid not in seen_nodes[source_node.node_type]:
                    seen_nodes[source_node.node_type].add(source_node.nid)
                if destination_node.nid not in seen_nodes[destination_node.node_type]:
                    seen_nodes[destination_node.node_type].add(destination_node.nid)

                edge_count += 1

                if edge_count % notify_threshold == 0:
                    percent_complete = (edge_count / total_count) * 100
                    print(f"Edge loading: {edge_count}/{total_count} ({percent_complete:.2f}%)")

        # Update app configurations
        async def _update_app_configuration(node: Node) -> None:
            # If the app has no link to a current_configuration, skip it.
            if "current_configuration" not in node.raw_data["_links"]:
                return

            # If the app has no services, it won't have a configuration, so skip it.
            if not node.raw_data["_embedded"]["services"]:
                return

            print(f"Retrieving the current configuration for {node.nid}")
            response = await self.client.get(
                node.raw_data["_links"]["current_configuration"]["href"]
            )

            if response.status_code != 200:
                print(f"Failed to retrieve the current configuration for {node.nid}")
                return

            node.raw_data["_embedded"]["current_configuration"] = response.json()

        async with anyio.create_task_group() as tg:
            async for node in graph.iter_nodes():
                if node.node_type == "aptible_app":
                    tg.start_soon(_update_app_configuration, node)

        total_nodes = sum(len(seen_nodes[node_type]) for node_type in seen_nodes)

        print(f"Initialized {edge_count} edges between {total_nodes} nodes")
        for node_type, node_ids in seen_nodes.items():
            print(f"  - {node_type}: {len(node_ids)}")
