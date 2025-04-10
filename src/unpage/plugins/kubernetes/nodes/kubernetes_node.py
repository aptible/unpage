from unpage.plugins.kubernetes.nodes.utils import label_key_value_to_node_id

from .base import KubernetesBaseNode


class KubernetesNode(KubernetesBaseNode):
    async def get_identifiers(self) -> list[str | None]:
        return [
            *await super().get_identifiers(),
            *[
                label_key_value_to_node_id(key, value)
                for key, value in self.raw_data.get("metadata", {}).get("labels", {}).items()
            ],
        ]

    async def get_reference_identifiers(self) -> list[str | None | tuple[str | None, str]]:
        return [
            *await super().get_reference_identifiers(),
            *[
                (a["address"], "running_on")
                for a in self.raw_data.get("status", {}).get("addresses", [])
                if "address" in a
            ],
        ]
