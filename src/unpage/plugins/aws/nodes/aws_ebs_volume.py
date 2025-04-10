from unpage.plugins.aws.nodes.base import AwsNode


class AwsEbsVolume(AwsNode):
    async def get_identifiers(self) -> list[str | None]:
        return [
            *await super().get_identifiers(),
            self.raw_data["VolumeId"],
        ]
