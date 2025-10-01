from unpage.plugins.gcp.nodes.base import GcpNode


class GcpForwardingRule(GcpNode):
    """A GCP Forwarding Rule (load balancer entry point)."""

    async def get_identifiers(self) -> list[str | None]:
        return [
            *await super().get_identifiers(),
            self.raw_data.get("id"),
            self.raw_data.get("name"),
            self.raw_data.get("IPAddress"),
            self.raw_data.get("selfLink"),
        ]

    async def get_reference_identifiers(
        self,
    ) -> list[str | None | tuple[str | None, str]]:
        references = [*await super().get_reference_identifiers()]

        # Add reference to target (target proxy or backend service)
        target = self.raw_data.get("target")
        if target:
            # Extract target name from URL
            target_name = target.split("/")[-1]
            references.append((target_name, "forwards_to"))

        # Add reference to backend service (for regional forwarding rules)
        backend_service = self.raw_data.get("backendService")
        if backend_service:
            backend_name = backend_service.split("/")[-1]
            references.append((backend_name, "routes_to"))

        return references
