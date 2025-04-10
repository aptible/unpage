from unpage.plugins.datadog.nodes.base import DatadogEntityNode


class DatadogSystem(DatadogEntityNode):
    """A node for a Datadog system."""

    async def get_identifiers(self) -> list[str | None]:
        return [
            *await super().get_identifiers(),
            f"system:default/{self.raw_data['attributes']['name']}",
        ]
