from typing import cast

from pydantic import AnyUrl, ValidationError

from .base import AptibleNode


class AptibleApp(AptibleNode):
    """A node representing an Aptible app resource."""

    async def get_identifiers(self) -> list[str | None]:
        """Return a list of unique identifiers for the node."""
        return [
            *await super().get_identifiers(),
            self.raw_data["handle"],
        ]

    async def get_reference_identifiers(
        self,
    ) -> list[str | None | tuple[str | None, str]]:
        """Return a list of identifiers that potentially reference other nodes."""
        return [
            *await super().get_reference_identifiers(),
            *await self._get_hostname_references(),
        ]

    async def _get_hostname_references(self) -> set[tuple[str, str]]:
        """Return a set of hostnames referenced by the app."""
        hostnames = set()

        try:
            env = cast("dict[str, str]", self.raw_data["_embedded"]["current_configuration"]["env"])
        except KeyError:
            return hostnames

        for value in env.values():
            try:
                url = AnyUrl(value)
            except ValidationError:
                continue
            if not url.host:
                continue
            hostnames.add(url.host)

        return {(hostname, "depends_on") for hostname in hostnames}
