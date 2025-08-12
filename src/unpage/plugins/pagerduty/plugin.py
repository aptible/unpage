import os
from collections.abc import AsyncGenerator
from typing import Any, cast

import questionary
from pagerduty.rest_api_v2_client import RestApiV2Client
from pydantic import AwareDatetime, BaseModel

from unpage.config.manager import PluginSettings
from unpage.plugins.base import Plugin
from unpage.plugins.mixins import McpServerMixin, tool
from unpage.plugins.pagerduty.models import PagerDutyIncident, PagerDutyIncidentPayload
from unpage.utils import classproperty


class PagerDutyPluginSettings(BaseModel):
    api_key: str = ""
    default_from: str = ""


class PagerDutyPlugin(Plugin, McpServerMixin):
    def __init__(
        self,
        *args: Any,
        api_key: str | None = None,
        default_from: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._api_key = api_key or os.getenv("PAGERDUTY_API_KEY", "")
        self.default_from = default_from or os.getenv("PAGERDUTY_DEFAULT_FROM")
        if self._api_key:
            self._client = RestApiV2Client(self._api_key, default_from=self.default_from)

    @classproperty
    def default_plugin_settings(cls) -> PluginSettings:
        return PagerDutyPluginSettings(
            api_key=os.environ.get("PAGERDUTY_API_KEY", ""),
            default_from=os.environ.get("PAGERDUTY_DEFAULT_FROM", ""),
        ).model_dump()

    async def interactive_configure(self) -> PluginSettings:
        defaults = self.default_plugin_settings
        return PagerDutyPluginSettings(
            api_key=await questionary.password(
                "API Key",
                default=self._api_key or defaults.get("api_key", ""),
                instruction="Generate a token with https://docs.aptible.ai/plugins/pagerduty#prerequisites",
            ).unsafe_ask_async(),
            default_from=await questionary.text(
                "Default User Email",
                default=self.default_from or defaults.get("default_user_email", ""),
                instruction="The email you provide will appear as the author for annotations left by the agent.",
            ).unsafe_ask_async(),
        ).model_dump()

    async def validate_plugin_config(self) -> None:
        if not self._api_key:
            raise LookupError(
                "plugins.pagerduty.settings.api_key (or $PAGERDUTY_API_KEY) must be set"
            )
        if not self.default_from:
            raise ValueError(
                "PagerDuty default_user_email may not be left empty or blank. Choose a user that will be used as the author when creating status updates."
            )
        for user in self._client.iter_all("users"):
            if user["email"].lower() == self.default_from.lower():
                return
        raise ValueError(f"No PagerDuty users have the email '{self.default_from}'")

    @tool()
    async def get_incident_details(self, incident_id: str) -> dict[str, Any]:
        """Get a PagerDuty incident by ID, including all alert details.

        Args:
            incident_id (str): The ID of the PagerDuty incident. Typically a
            string of uppercase letters and numbers. For example "PGR0VU2",
            "PF9KMXH", or "Q2K78SNJ5U1VE1".

        Returns:
            dict: The incident JSON payload, including all alert details.
        """
        incident = cast("dict[str, Any]", self._client.rget(f"/incidents/{incident_id}"))
        incident["alerts"] = await self.get_alert_details_for_incident(incident_id)
        return incident

    @tool()
    async def get_alert_details_for_incident(self, incident_id: str) -> list[dict[str, Any]]:
        """Get the details of the alert(s) for a PagerDuty incident.

        Args:
            incident_id (str): The ID of the PagerDuty incident. Typically a
            string of uppercase letters and numbers. For example "PGR0VU2",
            "PF9KMXH", or "Q2K78SNJ5U1VE1".

        Returns:
            list[dict]: The list of alert details.
        """
        return cast("list[dict[str, Any]]", self._client.rget(f"/incidents/{incident_id}/alerts"))

    @tool()
    async def post_status_update(self, incident_id: str, message: str) -> None:
        """Post a status update to a PagerDuty incident

        Args:
            incident_id (str): The PagerDuty ID of the incident
            message (str): The message to post
        """
        self._client.rpost(
            f"/incidents/{incident_id}/status_updates",
            json={
                "message": message,
            },
        )

    @tool()
    async def resolve_incident(
        self, incident_id: str, resolution_message: str | None = None
    ) -> None:
        """Resolve a PagerDuty incident

        Args:
            incident_id (str): The ID of the PagerDuty incident to resolve
            resolution_message (str, optional): A message to include with the resolution
        """
        data = {"incident": {"type": "incident", "status": "resolved"}}

        self._client.rput(
            f"/incidents/{incident_id}",
            json=data,
        )

        # If a resolution message was provided, add it as a status update
        if resolution_message:
            await self.post_status_update(incident_id, resolution_message)

    async def get_incident_by_id(self, incident_id: str) -> PagerDutyIncident:
        """Get a single incident by its id

        Args:
            incident_id (str): The PagerDuty ID of the incident

        Returns:
            PagerDutyIncident: the pagerduty incident data
        """
        return PagerDutyIncident(
            **cast("dict[str, Any]", self._client.rget(f"/incidents/{incident_id}"))
        )

    async def recent_incident_payloads(
        self, since: AwareDatetime | None = None, sort_by: str = "incident_number:desc"
    ) -> AsyncGenerator[PagerDutyIncidentPayload, None]:
        """Get a list of recent PagerDuty incidents.

        Returns:
            list: incident JSON payloads that can be used for demoing and testing agents
        """
        for _, incident in enumerate(
            self._client.iter_all(
                "incidents",
                params={
                    "statuses": ["triggered", "acknowledged", "resolved"],
                    "sort_by": sort_by,
                    **({"since": since.date().isoformat()} if since else {}),
                },
            )
        ):
            yield PagerDutyIncidentPayload(incident=PagerDutyIncident(**incident))
