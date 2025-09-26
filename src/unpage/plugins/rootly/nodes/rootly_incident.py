from unpage.knowledge import Node


class RootlyIncident(Node):
    """A Rootly incident node."""

    @property
    def incident_id(self) -> str:
        """Get the Rootly incident ID."""
        return self.raw_data["id"]

    @property
    def title(self) -> str:
        """Get the incident title."""
        return self.raw_data.get("attributes", {}).get("title", "")

    @property
    def status(self) -> str:
        """Get the incident status."""
        return self.raw_data.get("attributes", {}).get("status", "")

    async def get_identifiers(self) -> list[str | None]:
        """Get identifiers for this incident."""
        return [
            *await super().get_identifiers(),
            self.incident_id,
            self.title,
        ]
