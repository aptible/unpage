from unpage.plugins.datadog.nodes.base import DatadogEntityNode


class DatadogService(DatadogEntityNode):
    """A node for a Datadog service."""

    async def get_identifiers(self) -> list[str | None]:
        return [
            *await super().get_identifiers(),
            self.raw_data["id"],
            f"service:default/{self.raw_data['attributes']['name']}",
        ]
