"""
Azure SDK utilities and helpers for authentication, error handling, and common operations.
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from azure.core.credentials import TokenCredential
from azure.core.exceptions import (
    ClientAuthenticationError,
    HttpResponseError,
    ResourceNotFoundError,
    ServiceRequestError,
)
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.subscription import SubscriptionClient

logger = logging.getLogger(__name__)


class AzureAuthenticationError(Exception):
    """Raised when Azure authentication fails."""


class AzureAccessError(Exception):
    """Raised when Azure access is denied or resource is not found."""


async def get_default_credential() -> TokenCredential:
    """
    Get the default Azure credential.

    This uses DefaultAzureCredential which tries multiple authentication methods:
    1. Environment variables
    2. Managed Identity
    3. Azure CLI
    4. Azure PowerShell
    5. Interactive browser (if enabled)

    Returns:
        Azure TokenCredential instance

    Raises:
        AzureAuthenticationError: If authentication fails
    """
    try:
        credential = DefaultAzureCredential()
        # Test the credential by trying to get a token
        await asyncio.to_thread(credential.get_token, "https://management.azure.com/.default")
        return credential
    except Exception as e:
        raise AzureAuthenticationError(f"Azure authentication failed: {e!s}") from e


async def list_accessible_subscriptions(credential: TokenCredential) -> list[dict[str, Any]]:
    """
    List all Azure subscriptions accessible with the given credential.

    Args:
        credential: Azure TokenCredential

    Returns:
        List of subscription dictionaries with id, name, state, etc.

    Raises:
        AzureAccessError: If unable to list subscriptions
    """
    try:
        client = SubscriptionClient(credential)

        # Use asyncio.to_thread to make the sync call async
        subscription_list = await asyncio.to_thread(client.subscriptions.list)

        subscriptions = []
        for subscription in subscription_list:
            # Handle state which might be an enum or a string depending on Azure SDK version
            state = "Unknown"
            if subscription.state:
                state = (
                    subscription.state.value
                    if hasattr(subscription.state, "value")
                    else str(subscription.state)
                )

            subscriptions.append(
                {
                    "subscription_id": subscription.subscription_id,
                    "display_name": subscription.display_name,
                    "state": state,
                    "tenant_id": getattr(subscription, "tenant_id", None),
                }
            )

        return subscriptions

    except (ClientAuthenticationError, ServiceRequestError) as e:
        raise AzureAccessError(f"Failed to list Azure subscriptions: {e!s}") from e


async def list_accessible_resource_groups(
    credential: TokenCredential, subscription_id: str
) -> list[str]:
    """
    List all resource groups in a subscription.

    Args:
        credential: Azure TokenCredential
        subscription_id: Azure subscription ID

    Returns:
        List of resource group names

    Raises:
        AzureAccessError: If unable to list resource groups
    """
    try:
        client = ResourceManagementClient(credential, subscription_id)

        # Use asyncio.to_thread to make the sync call async
        rg_list = await asyncio.to_thread(client.resource_groups.list)

        return [rg.name for rg in rg_list if rg.name]

    except (ClientAuthenticationError, ServiceRequestError, HttpResponseError) as e:
        raise AzureAccessError(
            f"Failed to list resource groups for subscription {subscription_id}: {e!s}"
        ) from e


@asynccontextmanager
async def handle_azure_errors(service_name: str, operation: str = "") -> AsyncGenerator[None, None]:
    """
    Context manager to handle common Azure SDK errors gracefully.

    Args:
        service_name: Name of the Azure service (for logging)
        operation: Operation being performed (for logging)

    Yields:
        None

    This will catch and log Azure errors but not re-raise them,
    allowing the calling code to continue with other operations.
    """
    try:
        yield
    except ResourceNotFoundError:
        logger.warning(f"Azure {service_name} resource not found during {operation}")
    except ClientAuthenticationError:
        logger.error(f"Azure {service_name} authentication failed during {operation}")
    except HttpResponseError as e:
        if e.status_code == 403:
            logger.warning(
                f"Access denied for Azure {service_name} during {operation} (HTTP {e.status_code})"
            )
        elif e.status_code == 404:
            logger.warning(
                f"Azure {service_name} resource not found during {operation} (HTTP {e.status_code})"
            )
        else:
            logger.error(
                f"Azure {service_name} HTTP error during {operation}: "
                f"HTTP {e.status_code} - {e.message}"
            )
    except ServiceRequestError as e:
        logger.error(f"Azure {service_name} service error during {operation}: {e!s}")
    except Exception as e:
        logger.error(f"Unexpected error with Azure {service_name} during {operation}: {e!s}")


def normalize_location(location: str) -> str:
    """
    Normalize Azure location/region names.

    Azure locations can be returned in different formats:
    - "East US" vs "eastus"
    - "West Europe" vs "westeurope"

    Args:
        location: Azure location string

    Returns:
        Normalized location string (lowercase, no spaces)
    """
    if not location:
        return ""

    return location.lower().replace(" ", "")


def get_resource_tags_dict(azure_resource: object) -> dict[str, str]:
    """
    Extract tags from an Azure resource as a dictionary.

    Args:
        azure_resource: Azure resource object with potential tags attribute

    Returns:
        Dictionary of tags (empty if no tags)
    """
    try:
        tags = getattr(azure_resource, "tags", None)
        return dict(tags) if tags else {}
    except (TypeError, AttributeError):
        return {}


async def test_azure_connectivity(credential: TokenCredential, subscription_id: str) -> bool:
    """
    Test Azure connectivity and permissions.

    Args:
        credential: Azure TokenCredential
        subscription_id: Azure subscription ID to test

    Returns:
        True if connectivity and basic permissions work, False otherwise
    """
    try:
        # Try to list resource groups as a basic connectivity test
        await list_accessible_resource_groups(credential, subscription_id)
        return True
    except AzureAccessError:
        return False
