"""Utility functions for GCP plugin."""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from google.api_core import exceptions as gcp_exceptions

if TYPE_CHECKING:
    from google.auth.credentials import Credentials


@asynccontextmanager
async def swallow_gcp_client_access_errors(service_name: str):
    """
    Context manager to swallow GCP client access errors.

    Similar to AWS's swallow_boto_client_access_errors, this catches
    common GCP permission and access errors.
    """
    try:
        yield
    except gcp_exceptions.PermissionDenied:
        pass
    except gcp_exceptions.Forbidden:
        pass
    except gcp_exceptions.NotFound:
        pass
    except Exception:
        # Swallow other API errors as well to prevent failures
        # when querying resources
        pass


def ensure_gcp_credentials(credentials: "Credentials") -> None:
    """
    Ensure GCP credentials are valid.

    Args:
        credentials: Google Cloud credentials object

    Raises:
        ValueError: If credentials are invalid
    """
    if not credentials:
        raise ValueError("GCP credentials are required")

    if not credentials.valid:
        credentials.refresh(None)
