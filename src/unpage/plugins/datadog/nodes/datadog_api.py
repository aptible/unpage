from unpage.plugins.datadog.nodes.base import DatadogEntityNode


class DatadogApi(DatadogEntityNode):
    """A node for a Datadog API."""

    async def get_identifiers(self) -> list[str | None]:
        return [
            *await super().get_identifiers(),
            self.raw_data["id"],
            f"api:default/{self.raw_data['attributes']['name']}",
        ]
