from unpage.plugins.gcp.nodes.base import GcpNode


class GcpStorageBucket(GcpNode):
    """A Google Cloud Storage bucket."""

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
        return [*await super().get_reference_identifiers()]
