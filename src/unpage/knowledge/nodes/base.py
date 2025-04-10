import re
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
)

from unpage.utils import camel_to_snake, classproperty

if TYPE_CHECKING:
    from unpage.knowledge import Edge, Graph

NODE_REGISTRY: dict[str, type["Node"]] = {}

_NodeType = TypeVar("_NodeType", bound="Node")


class Node(BaseModel):
    node_id: str
    raw_data: dict[str, Any] = Field(default_factory=dict)

    _graph: "Graph"

    model_config = ConfigDict(ignored_types=(classproperty,))

    def __init__(self, *args: Any, _graph: "Graph", **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._graph = _graph

    @classproperty
    def _node_source(cls) -> str:
        match = re.match(r"^unpage\.plugins\.([^\.]+)\..*$", cls.__module__)
        if not match:
            raise ValueError(f"Node source not found for {cls.__module__}")
        return match.group(1)

    @classproperty
    def _node_type(cls) -> str:
        return camel_to_snake(cls.__name__)

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        """Register the node type in the registry."""
        super().__pydantic_init_subclass__(**kwargs)

        key = f"{cls._node_source}:{cls._node_type}"

        if key in NODE_REGISTRY:
            raise ValueError(f"Node type {key} already registered")

        NODE_REGISTRY[key] = cls

    @computed_field
    @property
    def node_source(self) -> str:
        return self._node_source

    @computed_field
    @property
    def node_type(self) -> str:
        return self._node_type

    @computed_field
    @property
    def nid(self) -> str:
        """Return the canonical identifier for the node."""
        return ":".join(filter(bool, (self.node_source, self.node_type, self.node_id)))

    async def get_identifiers(self) -> list[str | None]:
        """Return a list of alternative identifiers for the node."""
        return []

    async def get_reference_identifiers(
        self,
    ) -> list[str | None | tuple[str | None, str]]:
        """Return a list of values from this node that may be references to other nodes.

        The values may be the referenced value, or tuples of the referenced value and the relationship type.
        """
        return []

    async def iter_successors(self) -> AsyncIterator["Node"]:
        """Return a list of nodes that are successors of this node."""
        async for successor in self._graph.iter_successors(self):
            yield successor

    async def iter_predecessors(self) -> AsyncIterator["Node"]:
        """Return a list of nodes that are predecessors of this node."""
        async for predecessor in self._graph.iter_predecessors(self):
            yield predecessor

    async def iter_neighbors(self) -> AsyncIterator["Node"]:
        """Return a list of nodes that are neighbors of this node."""
        async for neighbor in self._graph.iter_neighbors(self):
            yield neighbor

    async def iter_neighboring(
        self,
        only_type: type[_NodeType] | tuple[type[_NodeType], ...],
    ) -> AsyncIterator[_NodeType]:
        """Return a list of nodes that are neighbors of this node and are of a specific type."""
        async for neighbor in self._graph.iter_neighboring(self, only_type):
            yield neighbor

    async def iter_neighborhood_edges(self, max_depth: int = 1) -> AsyncIterator["Edge"]:
        """Return a list of edges that are neighbors of this node."""
        async for edge in self._graph.iter_neighborhood_edges(self, max_depth):
            yield edge
