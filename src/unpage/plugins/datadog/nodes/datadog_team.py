from unpage.plugins.datadog.nodes.base import DatadogNode


class DatadogTeam(DatadogNode):
    """A node for a Datadog team."""

    async def get_identifiers(self) -> list[str | None]:
        return [
            *await super().get_identifiers(),
            self.raw_data["id"],
            f"team:default/{self.raw_data['attributes']['handle']}",
        ]
