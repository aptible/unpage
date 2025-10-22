"""Utility functions for GCP plugin."""

import shutil
import subprocess
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import aiohttp
from google.auth import default, exceptions
from google.auth.transport import requests as google_requests

if TYPE_CHECKING:
    from google.auth.credentials import Credentials


async def list_accessible_regions_for_service(
    project_id: str, service: str, credentials: "Credentials"
) -> list[str]:
    """Return a list of regions available for a given GCP service."""

    # Get access token
    if not credentials.valid:
        request = google_requests.Request()
        credentials.refresh(request)

    token = credentials.token
    headers = {"Authorization": f"Bearer {token}"}

    # Map service names to their region list endpoints
    region_endpoints = {
        "compute": f"https://compute.googleapis.com/compute/v1/projects/{project_id}/regions",
        "sql": f"https://sqladmin.googleapis.com/v1/projects/{project_id}/regions",
        "storage": None,  # Storage is global
        "run": f"https://run.googleapis.com/v2/projects/{project_id}/locations",
        "functions": f"https://cloudfunctions.googleapis.com/v2/projects/{project_id}/locations",
    }

    endpoint = region_endpoints.get(service)
    if endpoint is None:
        # Service doesn't have regions (like storage) or is not recognized
        return []

    try:
        async with (
            aiohttp.ClientSession() as session,
            session.get(endpoint, headers=headers) as response,
        ):
            if response.status == 200:
                data = await response.json()

                # Extract region/location names based on service
                if service in ["compute", "sql"]:
                    items = data.get("items", [])
                    return [item["name"] for item in items if "name" in item]
                elif service in ["run", "functions"]:
                    locations = data.get("locations", [])
                    return [loc["locationId"] for loc in locations if "locationId" in loc]
                else:
                    return []
            else:
                print(f"Failed to list regions for {service}: {response.status}")
                return []
    except Exception as e:
        print(f"Error listing regions for {service}: {e}", file=sys.stderr)
        return []


async def list_gcp_projects(credentials: "Credentials") -> list[dict[str, str]]:
    """List all GCP projects accessible with the given credentials."""

    # Get access token
    if not credentials.valid:
        request = google_requests.Request()
        credentials.refresh(request)

    token = credentials.token
    headers = {"Authorization": f"Bearer {token}"}

    url = "https://cloudresourcemanager.googleapis.com/v1/projects"
    projects = []

    try:
        async with aiohttp.ClientSession() as session:
            page_token = None
            while True:
                params = {"pageSize": 100}
                if page_token:
                    params["pageToken"] = page_token

                async with session.get(url, headers=headers, params=params) as response:
                    if response.status != 200:
                        print(f"Failed to list projects: {response.status}")
                        break

                    data = await response.json()

                    projects.extend(
                        {
                            "projectId": project.get("projectId", ""),
                            "name": project.get("name", ""),
                            "projectNumber": project.get("projectNumber", ""),
                        }
                        for project in data.get("projects", [])
                        if project.get("lifecycleState") == "ACTIVE"
                    )

                    page_token = data.get("nextPageToken")
                    if not page_token:
                        break

    except Exception as e:
        print(f"Error listing GCP projects: {e}", file=sys.stderr)

    return projects


@asynccontextmanager
async def swallow_gcp_api_errors(
    service_name: str | None = None,
    region: str | None = None,
) -> AsyncIterator[None]:
    """Context manager to handle GCP API permission errors gracefully."""
    try:
        yield
    except aiohttp.ClientResponseError as e:
        if e.status in [403, 401]:  # Forbidden or Unauthorized
            location = f" in {region}" if region else ""
            print(
                f"Ignoring access denied for {service_name or 'GCP API'}{location}: {e.message}",
                file=sys.stderr,
            )
            return
        raise
    except Exception as e:
        if "403" in str(e) or "401" in str(e) or "permission" in str(e).lower():
            location = f" in {region}" if region else ""
            print(
                f"Ignoring permission error for {service_name or 'GCP API'}{location}: {e}",
                file=sys.stderr,
            )
            return
        raise


async def ensure_gcp_credentials(credentials: "Credentials") -> bool:
    """Ensure GCP credentials are valid and refresh if needed."""
    try:
        if not credentials.valid:
            request = google_requests.Request()
            credentials.refresh(request)
        return True
    except Exception as e:
        print(f"Failed to validate GCP credentials: {e}", file=sys.stderr)
        return False


def get_gcloud_default_project() -> str | None:
    """Get the default project from gcloud config."""
    try:
        gcloud_cli = shutil.which("gcloud") or "gcloud"
        result = subprocess.run(
            [gcloud_cli, "config", "get-value", "project"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except FileNotFoundError:
        # gcloud CLI not installed
        pass
    return None


def get_available_auth_methods() -> list[str]:
    """Detect which authentication methods are available."""
    available = []

    # Check for Application Default Credentials (ADC)
    # This includes credentials from: gcloud auth application-default login,
    # environment variables, or service accounts on GCP compute resources
    try:
        credentials, _ = default()
        if credentials:
            available.append("adc")
    except exceptions.DefaultCredentialsError:
        pass

    # Service account is always an option if user provides a key file
    available.append("service_account")

    return available


async def paginate_gcp_api(
    url: str,
    credentials: "Credentials",
    params: dict | None = None,
    items_key: str = "items",
    max_results_per_page: int = 100,
    page_size_param: str = "maxResults",
) -> AsyncIterator[dict]:
    """Paginate through GCP API results.

    Args:
        url: The API endpoint URL
        credentials: GCP credentials
        params: Additional query parameters
        items_key: The key in the response containing the items list
        max_results_per_page: Maximum results per page
        page_size_param: The parameter name for page size (e.g., "maxResults" or "pageSize")
    """

    # Get access token
    if not credentials.valid:
        request = google_requests.Request()
        credentials.refresh(request)

    token = credentials.token
    headers = {"Authorization": f"Bearer {token}"}

    if params is None:
        params = {}

    params[page_size_param] = max_results_per_page
    page_token = None

    async with aiohttp.ClientSession() as session:
        while True:
            if page_token:
                params["pageToken"] = page_token

            async with session.get(url, headers=headers, params=params) as response:
                if response.status >= 400:
                    error_text = await response.text()
                    raise Exception(f"GCP API error ({response.status}): {error_text}")

                data = await response.json()

                # Yield items from this page
                for item in data.get(items_key, []):
                    yield item

                # Check for next page
                page_token = data.get("nextPageToken")
                if not page_token:
                    break
