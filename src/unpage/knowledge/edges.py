from typing import Any

from pydantic import BaseModel

from .nodes import Node


class Edge(BaseModel):
    source_node: Node
    destination_node: Node
    properties: dict[str, Any]
