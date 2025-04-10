from .base import KubernetesBaseNode


class KubernetesNamespace(KubernetesBaseNode):
    async def get_identifiers(self) -> list[str | None]:
        return [
            *await super().get_identifiers(),
        ]

    async def get_reference_identifiers(self) -> list[str | None | tuple[str | None, str]]:
        return [
            *await super().get_reference_identifiers(),
        ]
