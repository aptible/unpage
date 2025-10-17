from unpage.knowledge.graph import Graph
from unpage.plugins.kubernetes.nodes.kubernetes_node import KubernetesNode
from unpage.plugins.kubernetes.nodes.utils import label_key_value_to_node_id

from .base import KubernetesBaseNode


class KubernetesPod(KubernetesBaseNode):
    async def get_identifiers(self) -> list[str | None]:
        return [
            *await super().get_identifiers(),
            *[i.get("ip") for i in self.raw_data.get("status", {}).get("podIPs", []) if "ip" in i],
            *[
                label_key_value_to_node_id(key, value)
                for key, value in self.raw_data.get("metadata", {}).get("labels", {}).items()
            ],
        ]

    async def get_reference_identifiers(self) -> list[str | None | tuple[str | None, str]]:
        references = [
            *await super().get_reference_identifiers(),
            (self.raw_data.get("spec", {}).get("nodeName"), "is_on_node"),
            (self.raw_data.get("spec", {}).get("serviceAccount"), "has_service_account"),
        ]

        # Only add the running_on reference if nodeName exists
        node_name = self.raw_data.get("spec", {}).get("nodeName")
        if node_name:
            references.append(
                (
                    KubernetesNode(node_id=node_name, _graph=Graph()).nid,
                    "running_on",
                )
            )

        return references
