from unpage.plugins.gcp.nodes.base import GcpNode


class GcpPersistentDisk(GcpNode):
    """A Google Compute Engine persistent disk."""

    async def get_identifiers(self) -> list[str | None]:
        return [
            *await super().get_identifiers(),
            self.raw_data.get("id"),
            self.raw_data.get("name"),
            self.raw_data.get("selfLink"),
        ]

    async def get_reference_identifiers(
        self,
    ) -> list[str | None | tuple[str | None, str]]:
        references = [*await super().get_reference_identifiers()]

        # Add references to instances using this disk
        for user in self.raw_data.get("users", []):
            # Extract instance name from URL
            instance_name = user.split("/")[-1]
            references.append((instance_name, "attached_to"))

        return references
