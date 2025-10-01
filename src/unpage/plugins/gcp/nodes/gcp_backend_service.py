from unpage.plugins.gcp.nodes.base import GcpNode


class GcpBackendService(GcpNode):
    """A GCP Backend Service (similar to AWS Target Group)."""

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

        # Add references to backend instances/groups
        for backend in self.raw_data.get("backends", []):
            group = backend.get("group")
            if group:
                # Extract instance group name from URL
                group_name = group.split("/")[-1]
                references.append((group_name, "routes_to"))

        return references
