from unpage.plugins.kubernetes.nodes.utils import label_key_value_to_node_id

from .base import KubernetesBaseNode


class KubernetesService(KubernetesBaseNode):
    async def get_identifiers(self) -> list[str | None]:
        identifiers = [
            *await super().get_identifiers(),
            *self.raw_data.get("spec", {}).get("clusterIPs", []),
        ]

        # Add namespace/name identifier for matching with GCP load balancers
        # GCP target pools reference services as "namespace/service-name"
        metadata = self.raw_data.get("metadata", {})
        namespace = metadata.get("namespace")
        name = metadata.get("name")
        if namespace and name:
            identifiers.append(f"{namespace}/{name}")

        # Add LoadBalancer ingress IPs as identifiers for matching
        identifiers.extend(
            ingress["ip"]
            for ingress in self.raw_data.get("status", {})
            .get("loadBalancer", {})
            .get("ingress", [])
            if "ip" in ingress
        )

        return identifiers

    async def get_reference_identifiers(self) -> list[str | None | tuple[str | None, str]]:
        return [
            *await super().get_reference_identifiers(),
            *[
                (label_key_value_to_node_id(key, value), "has_selector")
                for key, value in self.raw_data.get("spec", {}).get("selector", {}).items()
            ],
            *[
                (i.get("hostname"), "receives_traffic_from")
                for i in self.raw_data.get("status", {}).get("loadBalancer", {}).get("ingress", [])
                if "hostname" in i
            ],
        ]
