import weakref
from collections.abc import AsyncGenerator

from datadog_api_client import AsyncApiClient, Configuration
from datadog_api_client.v2.api.software_catalog_api import SoftwareCatalogApi
from datadog_api_client.v2.api.teams_api import TeamsApi
from datadog_api_client.v2.model.entity_data import EntityData
from datadog_api_client.v2.model.include_type import IncludeType
from datadog_api_client.v2.model.list_teams_include import ListTeamsInclude
from datadog_api_client.v2.model.team import Team


class DatadogClient:
    """A thin wrapper around the Datadog API client."""

    def __init__(self, api_key: str, application_key: str) -> None:
        self.client = AsyncApiClient(
            configuration=Configuration(
                api_key={
                    "apiKeyAuth": api_key,
                    "appKeyAuth": application_key,
                }
            )
        )
        # Register a finalizer to close the client when this object is garbage collected
        self._finalizer = weakref.finalize(self, lambda: self.client.close())

    async def iter_teams(self) -> AsyncGenerator[Team, None]:
        teams = TeamsApi(self.client)
        async for team in teams.list_teams_with_pagination(
            include=[ListTeamsInclude.USER_TEAM_PERMISSIONS]
        ):
            yield team

    async def iter_software_catalog_entities(
        self,
    ) -> AsyncGenerator[EntityData, None]:
        software_catalog = SoftwareCatalogApi(self.client)
        async for entity in software_catalog.list_catalog_entity_with_pagination(
            include=IncludeType.RELATION
        ):
            yield entity
