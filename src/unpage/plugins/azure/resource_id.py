"""
Azure Resource ID parser and utilities.

Azure Resource IDs follow the format:
/subscriptions/{subscription-id}/resourceGroups/{resource-group}/providers/{provider}/{resource-type}/{resource-name}
"""

import re
from typing import NamedTuple


class AzureResourceId(NamedTuple):
    """Parsed Azure Resource ID components."""

    subscription_id: str | None = None
    resource_group: str | None = None
    provider: str | None = None
    resource_type: str | None = None
    resource_name: str | None = None
    parent_resource: str | None = None  # For nested resources


def parse_resource_id(resource_id: str) -> AzureResourceId:
    """
    Parse an Azure Resource ID into its components.

    Args:
        resource_id: Full Azure Resource ID

    Returns:
        AzureResourceId with parsed components

    Examples:
        >>> parse_resource_id("/subscriptions/12345/resourceGroups/myRG/providers/Microsoft.Compute/virtualMachines/myVM")
        AzureResourceId(subscription_id='12345', resource_group='myRG', provider='Microsoft.Compute', resource_type='virtualMachines', resource_name='myVM')
    """
    if not resource_id or not resource_id.startswith("/"):
        return AzureResourceId()

    # Split the resource ID by '/' and remove empty strings
    parts = [part for part in resource_id.split("/") if part]

    if len(parts) < 2:
        return AzureResourceId()

    parsed = AzureResourceId()._asdict()

    try:
        # Parse basic structure
        i = 0
        while i < len(parts) - 1:
            key = parts[i].lower()
            value = parts[i + 1] if i + 1 < len(parts) else None

            if key == "subscriptions":
                parsed["subscription_id"] = value
            elif key == "resourcegroups":
                parsed["resource_group"] = value
            elif key == "providers":
                parsed["provider"] = value
                # Next part should be the resource type
                if i + 2 < len(parts):
                    parsed["resource_type"] = parts[i + 2]
                    i += 1  # Skip the resource type in next iteration
                # The part after resource type should be the resource name
                if i + 2 < len(parts):
                    parsed["resource_name"] = parts[i + 2]
                    i += 1  # Skip the resource name in next iteration

                    # Handle nested resources (e.g., databases within servers)
                    if i + 3 < len(parts):
                        # This could be a nested resource type and name
                        parsed["parent_resource"] = parsed["resource_name"]
                        parsed["resource_type"] = f"{parsed['resource_type']}/{parts[i + 2]}"
                        parsed["resource_name"] = parts[i + 3]
                        break
                break

            i += 2

    except (IndexError, AttributeError):
        # If parsing fails, return what we have
        pass

    return AzureResourceId(**parsed)


def build_resource_id(
    subscription_id: str,
    resource_group: str,
    provider: str,
    resource_type: str,
    resource_name: str,
    parent_resource: str | None = None,
) -> str:
    """
    Build an Azure Resource ID from components.

    Args:
        subscription_id: Azure subscription ID
        resource_group: Resource group name
        provider: Resource provider (e.g., Microsoft.Compute)
        resource_type: Resource type (e.g., virtualMachines)
        resource_name: Resource name
        parent_resource: Parent resource name for nested resources

    Returns:
        Full Azure Resource ID string
    """
    if parent_resource:
        # For nested resources like databases within servers
        parent_type = resource_type.split("/")[0] if "/" in resource_type else resource_type
        child_type = resource_type.split("/")[1] if "/" in resource_type else resource_type
        return (
            f"/subscriptions/{subscription_id}"
            f"/resourceGroups/{resource_group}"
            f"/providers/{provider}"
            f"/{parent_type}/{parent_resource}"
            f"/{child_type}/{resource_name}"
        )
    else:
        return (
            f"/subscriptions/{subscription_id}"
            f"/resourceGroups/{resource_group}"
            f"/providers/{provider}"
            f"/{resource_type}/{resource_name}"
        )


def get_resource_short_name(resource_id: str) -> str:
    """
    Get a short, human-readable name from a resource ID.

    Args:
        resource_id: Full Azure Resource ID

    Returns:
        Short name for the resource (typically the resource name)
    """
    parsed = parse_resource_id(resource_id)
    return parsed.resource_name or resource_id.split("/")[-1] if resource_id else ""


def is_valid_resource_id(resource_id: str) -> bool:
    """
    Check if a string is a valid Azure Resource ID.

    Args:
        resource_id: String to validate

    Returns:
        True if the string appears to be a valid Azure Resource ID
    """
    if not resource_id or not isinstance(resource_id, str):
        return False

    # Basic validation - should start with /subscriptions/
    pattern = r"^/subscriptions/[a-f0-9-]+/resourceGroups/[^/]+/providers/[^/]+/[^/]+/[^/]+.*$"
    return bool(re.match(pattern, resource_id, re.IGNORECASE))


def get_parent_resource_id(resource_id: str) -> str | None:
    """
    Get the parent resource ID for nested resources.

    Args:
        resource_id: Full Azure Resource ID

    Returns:
        Parent resource ID or None if not a nested resource
    """
    parsed = parse_resource_id(resource_id)

    if (
        parsed.parent_resource
        and parsed.subscription_id
        and parsed.resource_group
        and parsed.provider
    ):
        parent_type = (
            parsed.resource_type.split("/")[0]
            if parsed.resource_type and "/" in parsed.resource_type
            else parsed.resource_type
        )
        if parent_type:  # Ensure parent_type is not None
            return build_resource_id(
                subscription_id=parsed.subscription_id,
                resource_group=parsed.resource_group,
                provider=parsed.provider,
                resource_type=parent_type,
                resource_name=parsed.parent_resource,
            )

    return None
