import base64
import hashlib
import json
import os
import sys
import uuid
from importlib.metadata import version
from typing import Any

import httpx
import rich
import sentry_sdk

from unpage.config.manager import manager


def _get_or_create_user_id() -> str:
    identity_file = manager.config_root / ".identity"
    if not identity_file.exists():
        if not identity_file.parent.exists():
            identity_file.parent.mkdir(parents=True)
        identity_file.write_text(str(uuid.uuid4()))
    return identity_file.read_text().strip()


def hash_value(value: str) -> str:
    hasher = hashlib.sha256()
    hasher.update(value.encode("utf-8"))
    return base64.urlsafe_b64encode(hasher.digest()).decode("utf-8")


def prepare_profile_for_telemetry(profile: str) -> dict[str, Any]:
    return {
        "profile_sha256": hash_value(profile),
        **({"profile": "default"} if profile == "default" else {}),
    }


UNPAGE_TELEMETRY_DISABLED = os.getenv("UNPAGE_TELEMETRY_DISABLED", "false").lower() in (
    "1",
    "true",
    "yes",
)


_unpage_telemetry_log_events = os.getenv("UNPAGE_TELEMETRY_LOG_EVENTS", "false").lower() in (
    "1",
    "true",
    "yes",
)


class TunaClient(httpx.AsyncClient):
    BASE_URL = "https://tuna.aptible.com"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(
            *args,
            base_url=self.BASE_URL,
            headers={
                "Content-Type": "application/json; charset=utf-8",
            },
            timeout=httpx.Timeout(
                connect=30,
                read=30,
                write=45,
                pool=15,
            ),
            **kwargs,
        )
        self._user_id = _get_or_create_user_id()
        self._run_id = str(uuid.uuid4())

        # Check if telemetry is disabled globally
        active_config = manager.get_active_profile_config()
        self._telemetry_enabled = active_config.telemetry_enabled and not UNPAGE_TELEMETRY_DISABLED
        if not self._telemetry_enabled:
            # Let the user know that their preference is being respected
            print("Telemetry is disabled")
        if _unpage_telemetry_log_events:
            print("enabled telemetry event logging", file=sys.stderr)

    @property
    def user_id(self) -> str:
        """Unique user_id that is created for each invocation of the unpage program"""
        return self._user_id

    async def send_event(self, event: dict[str, Any]) -> None:
        """Record a telemetry event."""
        if not self._telemetry_enabled:
            return

        try:
            uname = os.uname()
            params = {
                "id": str(uuid.uuid4()),
                "user_id": self.user_id,
                "type": "unpage_telemetry",
                "url": "https://github.com/aptible/unpage",
                "value": json.dumps(
                    {
                        "version": version("unpage"),
                        "github": os.getenv("GITHUB_ACTIONS"),
                        "gitlab": os.getenv("GITLAB_CI"),
                        "travis": os.getenv("TRAVIS"),
                        "circleci": os.getenv("CIRCLECI"),
                        "sysname": uname.sysname,
                        "sysmachine": uname.machine,
                        "sysversion": uname.version,
                        "run_id": self._run_id,
                        **event,
                    }
                ),
            }
            if _unpage_telemetry_log_events:
                rich.print("unpage.telemetry.send_event", {"params": params}, file=sys.stderr)
            response = await self.get(
                "/www/e",
                params=params,
            )
            response.raise_for_status()
        except Exception as e:
            sentry_sdk.capture_exception(e)
            # Don't re-raise the exception (telemetry isn't critical)


client = TunaClient()
