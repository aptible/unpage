from typing import Any

from unpage.knowledge import Graph, Node


class AptibleNode(Node):
    """A node representing an Aptible resource."""

    async def get_identifiers(self) -> list[str | None]:
        """Return a list of unique identifiers for the node."""
        return [
            *await super().get_identifiers(),
            self.raw_data["_links"]["self"]["href"],
        ]

    async def get_reference_identifiers(
        self,
    ) -> list[str | None | tuple[str | None, str]]:
        """Return a list of identifiers that potentially reference other nodes."""
        return [
            *await super().get_reference_identifiers(),
            *await self._get_single_resource_references(),
        ]

    async def _get_single_resource_references(self) -> list[str]:
        """Return a list of HAL links that reference a single resource."""
        single_resource_references = []
        for key, link in self.raw_data["_links"].items():
            href = link["href"]
            # If the link is a single resource (the last segment is digits), add it to the list
            if not href.strip("/").rsplit("/", 1)[0].isdigit():
                single_resource_references.append((href, f"has_{key}"))

        return single_resource_references


def inflate_resource(resource: dict[str, Any], _graph: Graph) -> AptibleNode:
    from unpage.plugins.aptible.nodes.aptible_app import AptibleApp
    from unpage.plugins.aptible.nodes.aptible_aws_instance import AptibleAwsInstance
    from unpage.plugins.aptible.nodes.aptible_container import AptibleContainer
    from unpage.plugins.aptible.nodes.aptible_custom_resource import (
        AptibleCustomResource,
    )
    from unpage.plugins.aptible.nodes.aptible_database import AptibleDatabase
    from unpage.plugins.aptible.nodes.aptible_deployment import AptibleDeployment
    from unpage.plugins.aptible.nodes.aptible_disk import AptibleDisk
    from unpage.plugins.aptible.nodes.aptible_service import AptibleService
    from unpage.plugins.aptible.nodes.aptible_vhost import AptibleVhost

    try:
        return {
            "app": AptibleApp,
            "aws_instance": AptibleAwsInstance,
            "container": AptibleContainer,
            "custom_resource": AptibleCustomResource,
            "database": AptibleDatabase,
            "deployment": AptibleDeployment,
            "disk": AptibleDisk,
            "service": AptibleService,
            "vhost": AptibleVhost,
        }[resource["_type"]](
            **{
                "node_id": str(resource["id"]),
                "raw_data": resource,
                "_graph": _graph,
            }
        )
    except KeyError as ex:
        raise LookupError(f"Unknown resource type: {resource['_type']}") from ex
