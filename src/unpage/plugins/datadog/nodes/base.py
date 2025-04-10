import re

from unpage.knowledge import Node
from unpage.utils import camel_to_snake


class DatadogNode(Node):
    """A base class for Datadog nodes."""


class DatadogEntityNode(DatadogNode):
    """A base class for Datadog entity nodes."""

    _RELATED_ENTITY_REGEX = re.compile(
        r"^(?P<self_kind>[^:]+):(?P<self_namespace>[^/]+)/(?P<self_name>[^:]+):"
        r"RelationType(?P<relation>[^:]+):"
        r"(?P<other_kind>[^:]+):(?P<other_namespace>[^/]+)/(?P<other_name>[^:]+)$"
    )

    async def get_reference_identifiers(
        self,
    ) -> list[str | None | tuple[str | None, str]]:
        return [
            *await super().get_reference_identifiers(),
            *await self._get_related_entity_reference_identifiers(),
        ]

    async def _get_related_entity_reference_identifiers(
        self,
    ) -> list[tuple[str, str]]:
        """Get the reference identifiers for the related entities."""
        referenced_entity_identifiers: list[tuple[str, str]] = []

        related_entities = (
            self.raw_data.get("relationships", {}).get("related_entities", {}).get("data", [])
        )

        for related_entity in related_entities:
            parsed_id = self._RELATED_ENTITY_REGEX.match(related_entity["id"])

            if parsed_id is None:
                continue

            self_kind = parsed_id.group("self_kind")
            self_namespace = parsed_id.group("self_namespace")
            self_name = parsed_id.group("self_name")
            relation = camel_to_snake(parsed_id.group("relation"))
            other_kind = parsed_id.group("other_kind")
            other_namespace = parsed_id.group("other_namespace")
            other_name = parsed_id.group("other_name")

            print(
                f"{self_kind}:{self_namespace}/{self_name} --[{relation}]--> {other_kind}:{other_namespace}/{other_name}"
            )

            referenced_entity_identifiers.append(
                (
                    f"{other_kind}:{other_namespace}/{other_name}",
                    relation,
                )
            )

        return referenced_entity_identifiers
