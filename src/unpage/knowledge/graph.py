from collections import defaultdict
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar, cast

import anyio
import networkx as nx
from anyio import Lock
from pydantic_core import from_json, to_json, to_jsonable_python

from unpage.utils import generate_contrasting_colors, print, strip_secrets

from .edges import Edge
from .nodes import NODE_REGISTRY, Node

_NodeType = TypeVar("_NodeType", bound="Node")


class Graph:
    _lock: Lock
    _identifier_mapping: defaultdict[str, set[str]]
    _loaded_at: datetime | None

    def __init__(self, path: Path | str | None = None) -> None:
        self._lock = Lock()
        self._identifier_mapping = defaultdict(set)
        self._path = Path(path) if path else None
        self._loaded_at = None

    @property
    def digraph(self) -> nx.DiGraph:
        # If the file has changed since the last load, force a reload.
        if (
            self._path
            and self._loaded_at
            and self._path.stat().st_mtime > self._loaded_at.timestamp()
        ):
            print("Graph file has changed since last load, forcing reload...")
            self._loaded_at = None

        if not self._loaded_at:
            if self._path:
                if not self._path.exists():
                    self._digraph = nx.DiGraph()
                    self._path.write_bytes(
                        to_json(
                            nx.node_link_data(
                                self._digraph,
                                edges="edges",
                            ),
                            indent=2,
                        )
                    )

                json = from_json(self._path.read_bytes())
                self._digraph = nx.node_link_graph(json, edges="edges")
            else:
                self._digraph = nx.DiGraph()

            # Convert the nodes to the proper Node objects.
            for _nid, node in self._digraph.nodes(data=True):
                node_data = node.pop("data")
                node_key = ":".join([node_data["node_source"], node_data["node_type"]])
                node["data"] = NODE_REGISTRY[node_key](
                    **node_data,
                    _graph=self,
                )

            self._loaded_at = datetime.now(UTC)

        return self._digraph

    async def add_node(self, node: Node) -> None:
        """Add a node to the graph."""
        async with self._lock:
            self.digraph.add_node(node.nid, data=node)

            for identifier in (node.nid, *await node.get_identifiers()):
                if not identifier:
                    continue
                self._identifier_mapping[identifier].add(node.nid)

    async def get_node(self, nid: str) -> Node:
        """Get a node from the graph."""
        try:
            node = self.digraph.nodes[nid]
        except KeyError as ex:
            raise LookupError(f"Node {nid} not found in graph") from ex
        return node["data"]

    async def get_node_safe(self, nid: str) -> Node | None:
        """Get a node from the graph. Returns None if no Node found with nid."""
        try:
            return await self.get_node(nid)
        except LookupError:
            return None

    async def iter_nodes(self) -> AsyncIterator[Node]:
        """Get all nodes in the graph."""
        for _, node in self.digraph.nodes(data=True):
            yield cast("Node", node["data"])

    async def iter_predecessors(
        self,
        node: Node,
    ) -> AsyncIterator[Node]:
        """Get all predecessors of a node."""
        for predecessor_nid in self.digraph.predecessors(node.nid):
            yield self.digraph.nodes[predecessor_nid]["data"]

    async def iter_successors(self, node: Node) -> AsyncIterator[Node]:
        """Get all successors of a node."""
        for successor_nid in self.digraph.successors(node.nid):
            yield self.digraph.nodes[successor_nid]["data"]

    async def iter_neighbors(self, node: Node) -> AsyncIterator[Node]:
        """Get all neighbors of a node."""
        async for neighbor in self.iter_predecessors(node):
            yield neighbor

        async for neighbor in self.iter_successors(node):
            yield neighbor

    async def iter_neighboring(
        self,
        node: Node,
        only_type: type[_NodeType] | tuple[type[_NodeType], ...],
    ) -> AsyncIterator[_NodeType]:
        """Get all neighbors of a node that are of a specific type."""
        only_types = only_type if isinstance(only_type, tuple) else (only_type,)

        async for neighbor in self.iter_neighbors(node):
            if not isinstance(neighbor, only_types):
                continue
            yield cast("_NodeType", neighbor)

    async def iter_neighborhood_edges(self, node: Node, max_depth: int = 1) -> AsyncIterator[Edge]:
        """Get all edges in the neighborhood of a node."""
        for reverse in (True, False):
            for source_nid, destination_nid in nx.bfs_edges(
                self._digraph, node.nid, depth_limit=max_depth, reverse=reverse
            ):
                if reverse:
                    source_node = self.digraph.nodes[destination_nid]["data"]
                    destination_node = self.digraph.nodes[source_nid]["data"]
                else:
                    source_node = self.digraph.nodes[source_nid]["data"]
                    destination_node = self.digraph.nodes[destination_nid]["data"]

                properties = (
                    self.digraph.edges[source_nid, destination_nid]
                    if not reverse
                    else self.digraph.edges[destination_nid, source_nid]
                )

                yield Edge(
                    source_node=source_node,
                    destination_node=destination_node,
                    properties=properties,
                )

    async def add_edge(self, edge: Edge) -> None:
        """Add an edge between nodes to the graph."""
        async with self._lock:
            self.digraph.add_node(edge.source_node.nid, data=edge.source_node)
            self.digraph.add_node(edge.destination_node.nid, data=edge.destination_node)

            edge_properties = edge.properties
            if "relationship_type" in edge_properties:
                edge_properties["label"] = edge_properties["relationship_type"]

            self.digraph.add_edge(
                edge.source_node.nid,
                edge.destination_node.nid,
                **edge_properties,
            )

    async def iter_edges(self) -> AsyncIterator[Edge]:
        """Get all edges in the graph."""
        for source_nid, destination_nid, properties in self.digraph.edges(data=True):
            source_node = self.digraph.nodes[source_nid]["data"]
            destination_node = self.digraph.nodes[destination_nid]["data"]

            yield Edge(
                source_node=source_node,
                destination_node=destination_node,
                properties=properties,
            )

    async def infer_edges(self) -> None:
        """Infer edges between nodes based on the identifier mapping."""
        edge_count = self.digraph.number_of_edges()
        limiter = anyio.CapacityLimiter(24)
        async with anyio.create_task_group() as tg:
            async for node in self.iter_nodes():
                tg.start_soon(self._infer_edges_for_node, node, limiter)
        print(f"Inferred {self.digraph.number_of_edges() - edge_count} edges")

    async def _infer_edges_for_node(self, node: Node, limiter: anyio.CapacityLimiter) -> None:
        async with limiter:
            for ref in await node.get_reference_identifiers():
                if isinstance(ref, tuple) and len(ref) == 2:
                    reference_identifier, relationship_type = ref
                else:
                    reference_identifier = ref
                    relationship_type = "related_to"

                if not reference_identifier:
                    continue

                related_node_ids = self._identifier_mapping.get(reference_identifier, set())

                if not related_node_ids:
                    continue

                if len(related_node_ids) > 1:
                    # TODO: Handle multiple related nodes (i.e. ambiguous edges).
                    continue

                related_node_id = next(iter(related_node_ids))
                related_node = await self.get_node(related_node_id)

                print(f"Inferred edge: {node.nid} --[ {relationship_type} ]--> {related_node.nid}")

                await self.add_edge(
                    Edge(
                        source_node=node,
                        destination_node=related_node,
                        properties={
                            "relationship_type": relationship_type,
                        },
                    )
                )

    async def get_topology(self) -> "Graph":
        topology = Graph()

        async for edge in self.iter_edges():
            source_node = edge.source_node.model_copy(update={"node_id": ""})
            destination_node = edge.destination_node.model_copy(update={"node_id": ""})

            # Add nodes (types) and edge between them
            await topology.add_edge(
                Edge(
                    source_node=source_node,
                    destination_node=destination_node,
                    properties={"label": edge.properties["relationship_type"]},
                )
            )

        return topology

    async def to_pydot(self) -> str:
        """Convert the graph to a Pydot graph."""
        node_types = {f"{node.node_source}:{node.node_type}" async for node in self.iter_nodes()}
        node_colors = dict(
            zip(node_types, generate_contrasting_colors(len(node_types)), strict=True)
        )

        graph: nx.DiGraph = nx.relabel_nodes(
            self._digraph,
            # The mapping can be a callable, despite the type hint.
            #
            # We also quote the labels, since identifiers can often contain
            # colons, which are special in Pydot.
            mapping=lambda old: f'"{old}"',  # type: ignore
            copy=True,
        )

        # Set the defaults.
        graph.graph["graph"] = {"nodesep": 1}
        graph.graph["node"] = {
            "shape": "box",
            "style": "rounded,filled",
            "fontname": "Helvetica",
            "margin": "0.25",
        }

        # Set the node colors.
        for _, node in graph.nodes(data=True):
            node_data = cast("Node", node["data"])
            node_key = f"{node_data.node_source}:{node_data.node_type}"
            fill_color, font_color = node_colors[node_key]
            node["fillcolor"] = fill_color
            node["fontcolor"] = font_color
            del node["data"]

        return nx.nx_pydot.to_pydot(graph)

    async def save(self, path: Path | str) -> None:
        """Save the graph to a file."""
        async with self._lock:
            data = nx.node_link_data(self._digraph, edges="edges")
            print("Scrubbing secrets from graph...")
            cleaned_data = strip_secrets(to_jsonable_python(data))
            path = Path(path)
            path.write_bytes(
                to_json(
                    {
                        **cleaned_data,
                        "_identifier_mapping": dict(self._identifier_mapping),
                    },
                    indent=2,
                )
            )
