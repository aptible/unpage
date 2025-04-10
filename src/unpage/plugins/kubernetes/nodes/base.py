from unpage.knowledge.graph import Node


class KubernetesBaseNode(Node):
    async def get_identifiers(self) -> list[str | None]:
        return [
            *await super().get_identifiers(),
            self.raw_data.get("metadata", {}).get("uid"),
            self.raw_data.get("metadata", {}).get("name"),
        ]

    async def get_reference_identifiers(self) -> list[str | None | tuple[str | None, str]]:
        return [
            *await super().get_reference_identifiers(),
            *[
                (owner_ref.get("uid", None), "owned_by")
                for owner_ref in self.raw_data.get("metadata", {}).get("ownerReferences", [])
            ],
        ]
