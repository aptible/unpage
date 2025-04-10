from unpage.plugins.aptible.nodes.base import AptibleNode


class AptibleAwsInstance(AptibleNode):
    async def get_identifiers(self) -> list[str | None]:
        return [
            *await super().get_identifiers(),
            self.raw_data["name"],
        ]

    async def get_reference_identifiers(
        self,
    ) -> list[str | None | tuple[str | None, str]]:
        return [
            *await super().get_reference_identifiers(),
            (self.raw_data["instance_id"], "represents"),
        ]
