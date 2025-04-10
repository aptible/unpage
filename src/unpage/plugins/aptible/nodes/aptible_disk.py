from unpage.plugins.aptible.nodes.base import AptibleNode


class AptibleDisk(AptibleNode):
    async def get_reference_identifiers(
        self,
    ) -> list[str | None | tuple[str | None, str]]:
        return [
            *await super().get_reference_identifiers(),
            (self.raw_data["ebs_volume_id"], "represents"),
            (self.raw_data["host"], "mounted_to"),
        ]
