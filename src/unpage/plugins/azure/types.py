"""
Type-safe data classes for Azure resources.

These classes provide proper type annotations for Azure SDK objects
that lack complete type information.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class AzureServer:
    """Type-safe representation of an Azure database server."""

    id: str
    name: str
    type: str | None = None
    location: str | None = None
    resource_group: str | None = None
    raw_data: dict[str, Any] | None = None

    @classmethod
    def from_sdk_object(cls, obj: object) -> "AzureServer | None":
        """Create from Azure SDK server object."""
        server_id = getattr(obj, "id", None)
        server_name = getattr(obj, "name", None)

        if not (server_id and server_name):
            return None

        return cls(
            id=server_id,
            name=server_name,
            type=getattr(obj, "type", None),
            location=getattr(obj, "location", None),
            resource_group=server_id.split("/")[4] if "/" in server_id else None,
            raw_data=obj.as_dict() if hasattr(obj, "as_dict") and callable(obj.as_dict) else None,  # type: ignore[attr-defined]
        )


@dataclass
class AzureDatabase:
    """Type-safe representation of an Azure database."""

    id: str
    name: str
    type: str | None = None
    location: str | None = None
    edition: str | None = None
    service_level_objective: str | None = None
    status: str | None = None
    collation: str | None = None
    max_size_bytes: int | None = None
    creation_date: str | None = None
    charset: str | None = None
    raw_data: dict[str, Any] | None = None

    @classmethod
    def from_sdk_object(cls, obj: object) -> "AzureDatabase | None":
        """Create from Azure SDK database object."""
        db_id = getattr(obj, "id", None)
        db_name = getattr(obj, "name", None)

        if not (db_id and db_name):
            return None

        creation_date = getattr(obj, "creation_date", None)
        if creation_date and hasattr(creation_date, "isoformat"):
            creation_date = creation_date.isoformat()

        max_size = getattr(obj, "max_size_bytes", None)
        if max_size is not None:
            try:
                max_size = int(max_size)
            except (TypeError, ValueError):
                max_size = None

        return cls(
            id=db_id,
            name=db_name,
            type=getattr(obj, "type", None),
            location=getattr(obj, "location", None),
            edition=getattr(obj, "edition", None),
            service_level_objective=getattr(obj, "service_level_objective", None),
            status=getattr(obj, "status", None),
            collation=getattr(obj, "collation", None),
            max_size_bytes=max_size,
            creation_date=str(creation_date) if creation_date else None,
            charset=getattr(obj, "charset", None),
            raw_data=obj.as_dict() if hasattr(obj, "as_dict") and callable(obj.as_dict) else None,  # type: ignore[attr-defined]
        )


@dataclass
class AzureVirtualMachine:
    """Type-safe representation of an Azure VM."""

    id: str
    name: str
    type: str | None = None
    location: str | None = None
    vm_size: str | None = None
    provisioning_state: str | None = None
    raw_data: dict[str, Any] | None = None

    @classmethod
    def from_sdk_object(cls, obj: object) -> "AzureVirtualMachine | None":
        """Create from Azure SDK VM object."""
        vm_id = getattr(obj, "id", None)
        vm_name = getattr(obj, "name", None)

        if not vm_id:
            return None

        # Extract VM size from hardware_profile if available
        vm_size = None
        hardware_profile = getattr(obj, "hardware_profile", None)
        if hardware_profile:
            vm_size = getattr(hardware_profile, "vm_size", None)

        return cls(
            id=vm_id,
            name=vm_name or vm_id.split("/")[-1] if "/" in vm_id else "unknown",
            type=getattr(obj, "type", None),
            location=getattr(obj, "location", None),
            vm_size=vm_size,
            provisioning_state=getattr(obj, "provisioning_state", None),
            raw_data=obj.as_dict() if hasattr(obj, "as_dict") and callable(obj.as_dict) else None,  # type: ignore[attr-defined]
        )


@dataclass
class AzureLoadBalancer:
    """Type-safe representation of an Azure Load Balancer."""

    id: str
    name: str
    type: str | None = None
    location: str | None = None
    sku_name: str | None = None
    sku_tier: str | None = None
    provisioning_state: str | None = None
    raw_data: dict[str, Any] | None = None

    @classmethod
    def from_sdk_object(cls, obj: object) -> "AzureLoadBalancer | None":
        """Create from Azure SDK Load Balancer object."""
        lb_id = getattr(obj, "id", None)
        lb_name = getattr(obj, "name", None)

        if not lb_id:
            return None

        # Extract SKU info if available
        sku_name = None
        sku_tier = None
        sku = getattr(obj, "sku", None)
        if sku:
            sku_name = getattr(sku, "name", None)
            sku_tier = getattr(sku, "tier", None)

        return cls(
            id=lb_id,
            name=lb_name or lb_id.split("/")[-1] if "/" in lb_id else "unknown",
            type=getattr(obj, "type", None),
            location=getattr(obj, "location", None),
            sku_name=sku_name,
            sku_tier=sku_tier,
            provisioning_state=getattr(obj, "provisioning_state", None),
            raw_data=obj.as_dict() if hasattr(obj, "as_dict") and callable(obj.as_dict) else None,  # type: ignore[attr-defined]
        )


@dataclass
class AzureStorageAccount:
    """Type-safe representation of an Azure Storage Account."""

    id: str
    name: str
    type: str | None = None
    location: str | None = None
    kind: str | None = None
    sku_name: str | None = None
    sku_tier: str | None = None
    provisioning_state: str | None = None
    raw_data: dict[str, Any] | None = None

    @classmethod
    def from_sdk_object(cls, obj: object) -> "AzureStorageAccount | None":
        """Create from Azure SDK Storage Account object."""
        storage_id = getattr(obj, "id", None)
        storage_name = getattr(obj, "name", None)

        if not storage_id:
            return None

        # Extract SKU info if available
        sku_name = None
        sku_tier = None
        sku = getattr(obj, "sku", None)
        if sku:
            sku_name = getattr(sku, "name", None)
            sku_tier = getattr(sku, "tier", None)

        return cls(
            id=storage_id,
            name=storage_name or storage_id.split("/")[-1] if "/" in storage_id else "unknown",
            type=getattr(obj, "type", None),
            location=getattr(obj, "location", None),
            kind=getattr(obj, "kind", None),
            sku_name=sku_name,
            sku_tier=sku_tier,
            provisioning_state=getattr(obj, "provisioning_state", None),
            raw_data=obj.as_dict() if hasattr(obj, "as_dict") and callable(obj.as_dict) else None,  # type: ignore[attr-defined]
        )


@dataclass
class AzureManagedDisk:
    """Type-safe representation of an Azure Managed Disk."""

    id: str
    name: str
    type: str | None = None
    location: str | None = None
    disk_size_gb: int | None = None
    disk_state: str | None = None
    sku_name: str | None = None
    provisioning_state: str | None = None
    raw_data: dict[str, Any] | None = None

    @classmethod
    def from_sdk_object(cls, obj: object) -> "AzureManagedDisk | None":
        """Create from Azure SDK Managed Disk object."""
        disk_id = getattr(obj, "id", None)
        disk_name = getattr(obj, "name", None)

        if not disk_id:
            return None

        # Extract disk size
        disk_size = getattr(obj, "disk_size_gb", None)
        if disk_size is not None:
            try:
                disk_size = int(disk_size)
            except (TypeError, ValueError):
                disk_size = None

        # Extract SKU info if available
        sku_name = None
        sku = getattr(obj, "sku", None)
        if sku:
            sku_name = getattr(sku, "name", None)

        return cls(
            id=disk_id,
            name=disk_name or disk_id.split("/")[-1] if "/" in disk_id else "unknown",
            type=getattr(obj, "type", None),
            location=getattr(obj, "location", None),
            disk_size_gb=disk_size,
            disk_state=getattr(obj, "disk_state", None),
            sku_name=sku_name,
            provisioning_state=getattr(obj, "provisioning_state", None),
            raw_data=obj.as_dict() if hasattr(obj, "as_dict") and callable(obj.as_dict) else None,  # type: ignore[attr-defined]
        )


@dataclass
class AzureCosmosAccount:
    """Type-safe representation of an Azure Cosmos DB Account."""

    id: str
    name: str
    type: str | None = None
    location: str | None = None
    kind: str | None = None
    document_endpoint: str | None = None
    provisioning_state: str | None = None
    raw_data: dict[str, Any] | None = None

    @classmethod
    def from_sdk_object(cls, obj: object) -> "AzureCosmosAccount | None":
        """Create from Azure SDK Cosmos DB Account object."""
        cosmos_id = getattr(obj, "id", None)
        cosmos_name = getattr(obj, "name", None)

        if not cosmos_id:
            return None

        return cls(
            id=cosmos_id,
            name=cosmos_name or cosmos_id.split("/")[-1] if "/" in cosmos_id else "unknown",
            type=getattr(obj, "type", None),
            location=getattr(obj, "location", None),
            kind=getattr(obj, "kind", None),
            document_endpoint=getattr(obj, "document_endpoint", None),
            provisioning_state=getattr(obj, "provisioning_state", None),
            raw_data=obj.as_dict() if hasattr(obj, "as_dict") and callable(obj.as_dict) else None,  # type: ignore[attr-defined]
        )


@dataclass
class AzureApplicationGateway:
    """Type-safe representation of an Azure Application Gateway."""

    id: str
    name: str
    type: str | None = None
    location: str | None = None
    sku_name: str | None = None
    sku_tier: str | None = None
    sku_capacity: int | None = None
    operational_state: str | None = None
    provisioning_state: str | None = None
    raw_data: dict[str, Any] | None = None

    @classmethod
    def from_sdk_object(cls, obj: object) -> "AzureApplicationGateway | None":
        """Create from Azure SDK Application Gateway object."""
        ag_id = getattr(obj, "id", None)
        ag_name = getattr(obj, "name", None)

        if not ag_id:
            return None

        # Extract SKU info if available
        sku_name = None
        sku_tier = None
        sku_capacity = None
        sku = getattr(obj, "sku", None)
        if sku:
            sku_name = getattr(sku, "name", None)
            sku_tier = getattr(sku, "tier", None)
            capacity = getattr(sku, "capacity", None)
            if capacity is not None:
                try:
                    sku_capacity = int(capacity)
                except (TypeError, ValueError):
                    sku_capacity = None

        return cls(
            id=ag_id,
            name=ag_name or ag_id.split("/")[-1] if "/" in ag_id else "unknown",
            type=getattr(obj, "type", None),
            location=getattr(obj, "location", None),
            sku_name=sku_name,
            sku_tier=sku_tier,
            sku_capacity=sku_capacity,
            operational_state=getattr(obj, "operational_state", None),
            provisioning_state=getattr(obj, "provisioning_state", None),
            raw_data=obj.as_dict() if hasattr(obj, "as_dict") and callable(obj.as_dict) else None,  # type: ignore[attr-defined]
        )


@dataclass
class AzureVmScaleSet:
    """Type-safe representation of an Azure VM Scale Set."""

    id: str
    name: str
    type: str | None = None
    location: str | None = None
    sku: dict[str, Any] | None = None
    capacity: int = 0
    provisioning_state: str | None = None
    raw_data: dict[str, Any] | None = None

    @classmethod
    def from_sdk_object(cls, obj: object) -> "AzureVmScaleSet | None":
        """Create from Azure SDK VM Scale Set object."""
        vmss_id = getattr(obj, "id", None)
        vmss_name = getattr(obj, "name", None)

        if not vmss_id:
            return None

        sku = getattr(obj, "sku", None)
        sku_dict = None
        capacity = 0
        if sku:
            sku_dict = {
                "name": getattr(sku, "name", None),
                "tier": getattr(sku, "tier", None),
                "capacity": getattr(sku, "capacity", 0),
            }
            capacity = sku_dict.get("capacity", 0)

        return cls(
            id=vmss_id,
            name=vmss_name or vmss_id.split("/")[-1] if "/" in vmss_id else "unknown",
            type=getattr(obj, "type", None),
            location=getattr(obj, "location", None),
            sku=sku_dict,
            capacity=capacity,
            provisioning_state=getattr(obj, "provisioning_state", None),
            raw_data=obj.as_dict() if hasattr(obj, "as_dict") and callable(obj.as_dict) else None,  # type: ignore[attr-defined]
        )


@dataclass
class AzureVmScaleSetInstance:
    """Type-safe representation of an Azure VM Scale Set Instance."""

    id: str
    name: str
    instance_id: str | None = None
    type: str | None = None
    location: str | None = None
    vm_id: str | None = None
    latest_model_applied: bool = False
    raw_data: dict[str, Any] | None = None

    @classmethod
    def from_sdk_object(cls, obj: object) -> "AzureVmScaleSetInstance | None":
        """Create from Azure SDK VM Scale Set Instance object."""
        instance_id = getattr(obj, "id", None)
        instance_name = getattr(obj, "name", None)

        if not instance_id:
            return None

        return cls(
            id=instance_id,
            name=instance_name or instance_id.split("/")[-1] if "/" in instance_id else "unknown",
            instance_id=getattr(obj, "instance_id", None),
            type=getattr(obj, "type", None),
            location=getattr(obj, "location", None),
            vm_id=getattr(obj, "vm_id", None),
            latest_model_applied=getattr(obj, "latest_model_applied", False),
            raw_data=obj.as_dict() if hasattr(obj, "as_dict") and callable(obj.as_dict) else None,  # type: ignore[attr-defined]
        )


@dataclass
class AzurePublicIpAddress:
    """Type-safe representation of an Azure Public IP Address."""

    id: str
    name: str
    type: str | None = None
    location: str | None = None
    ip_address: str | None = None
    allocation_method: str | None = None
    sku: dict[str, Any] | None = None
    dns_settings: dict[str, Any] | None = None
    raw_data: dict[str, Any] | None = None

    @classmethod
    def from_sdk_object(cls, obj: object) -> "AzurePublicIpAddress | None":
        """Create from Azure SDK Public IP Address object."""
        ip_id = getattr(obj, "id", None)
        ip_name = getattr(obj, "name", None)

        if not ip_id:
            return None

        sku = getattr(obj, "sku", None)
        sku_dict = None
        if sku:
            sku_dict = {
                "name": getattr(sku, "name", None),
                "tier": getattr(sku, "tier", None),
            }

        dns_settings = getattr(obj, "dns_settings", None)
        dns_dict = None
        if dns_settings:
            dns_dict = {
                "domain_name_label": getattr(dns_settings, "domain_name_label", None),
                "fqdn": getattr(dns_settings, "fqdn", None),
            }

        return cls(
            id=ip_id,
            name=ip_name or ip_id.split("/")[-1] if "/" in ip_id else "unknown",
            type=getattr(obj, "type", None),
            location=getattr(obj, "location", None),
            ip_address=getattr(obj, "ip_address", None),
            allocation_method=getattr(obj, "public_ip_allocation_method", None),
            sku=sku_dict,
            dns_settings=dns_dict,
            raw_data=obj.as_dict() if hasattr(obj, "as_dict") and callable(obj.as_dict) else None,  # type: ignore[attr-defined]
        )


@dataclass
class AzureVirtualNetwork:
    """Type-safe representation of an Azure Virtual Network."""

    id: str
    name: str
    type: str | None = None
    location: str | None = None
    address_space: list[str] | None = None
    raw_data: dict[str, Any] | None = None

    @classmethod
    def from_sdk_object(cls, obj: object) -> "AzureVirtualNetwork | None":
        """Create from Azure SDK Virtual Network object."""
        vnet_id = getattr(obj, "id", None)
        vnet_name = getattr(obj, "name", None)

        if not vnet_id:
            return None

        address_space = getattr(obj, "address_space", None)
        address_prefixes = None
        if address_space:
            address_prefixes = getattr(address_space, "address_prefixes", None)

        return cls(
            id=vnet_id,
            name=vnet_name or vnet_id.split("/")[-1] if "/" in vnet_id else "unknown",
            type=getattr(obj, "type", None),
            location=getattr(obj, "location", None),
            address_space=address_prefixes,
            raw_data=obj.as_dict() if hasattr(obj, "as_dict") and callable(obj.as_dict) else None,  # type: ignore[attr-defined]
        )


@dataclass
class AzureSubnet:
    """Type-safe representation of an Azure Subnet."""

    id: str
    name: str
    address_prefix: str | None = None
    raw_data: dict[str, Any] | None = None

    @classmethod
    def from_sdk_object(cls, obj: object) -> "AzureSubnet | None":
        """Create from Azure SDK Subnet object."""
        subnet_id = getattr(obj, "id", None)
        subnet_name = getattr(obj, "name", None)

        if not subnet_id:
            return None

        return cls(
            id=subnet_id,
            name=subnet_name or subnet_id.split("/")[-1] if "/" in subnet_id else "unknown",
            address_prefix=getattr(obj, "address_prefix", None),
            raw_data=obj.as_dict() if hasattr(obj, "as_dict") and callable(obj.as_dict) else None,  # type: ignore[attr-defined]
        )


@dataclass
class AzureNetworkSecurityGroup:
    """Type-safe representation of an Azure Network Security Group."""

    id: str
    name: str
    type: str | None = None
    location: str | None = None
    raw_data: dict[str, Any] | None = None

    @classmethod
    def from_sdk_object(cls, obj: object) -> "AzureNetworkSecurityGroup | None":
        """Create from Azure SDK Network Security Group object."""
        nsg_id = getattr(obj, "id", None)
        nsg_name = getattr(obj, "name", None)

        if not nsg_id:
            return None

        return cls(
            id=nsg_id,
            name=nsg_name or nsg_id.split("/")[-1] if "/" in nsg_id else "unknown",
            type=getattr(obj, "type", None),
            location=getattr(obj, "location", None),
            raw_data=obj.as_dict() if hasattr(obj, "as_dict") and callable(obj.as_dict) else None,  # type: ignore[attr-defined]
        )


@dataclass
class AzureNetworkInterface:
    """Type-safe representation of an Azure Network Interface."""

    id: str
    name: str
    type: str | None = None
    location: str | None = None
    mac_address: str | None = None
    primary: bool = False
    provisioning_state: str | None = None
    raw_data: dict[str, Any] | None = None

    @classmethod
    def from_sdk_object(cls, obj: object) -> "AzureNetworkInterface | None":
        """Create from Azure SDK Network Interface object."""
        nic_id = getattr(obj, "id", None)
        nic_name = getattr(obj, "name", None)

        if not nic_id:
            return None

        return cls(
            id=nic_id,
            name=nic_name or nic_id.split("/")[-1] if "/" in nic_id else "unknown",
            type=getattr(obj, "type", None),
            location=getattr(obj, "location", None),
            mac_address=getattr(obj, "mac_address", None),
            primary=getattr(obj, "primary", False),
            provisioning_state=getattr(obj, "provisioning_state", None),
            raw_data=obj.as_dict() if hasattr(obj, "as_dict") and callable(obj.as_dict) else None,  # type: ignore[attr-defined]
        )


@dataclass
class AzureAksCluster:
    """Type-safe representation of an Azure AKS Managed Cluster."""

    id: str
    name: str
    type: str | None = None
    location: str | None = None
    kubernetes_version: str | None = None
    fqdn: str | None = None
    provisioning_state: str | None = None
    power_state: dict[str, Any] | None = None
    raw_data: dict[str, Any] | None = None

    @classmethod
    def from_sdk_object(cls, obj: object) -> "AzureAksCluster | None":
        """Create from Azure SDK Managed Cluster object."""
        cluster_id = getattr(obj, "id", None)
        cluster_name = getattr(obj, "name", None)

        if not cluster_id:
            return None

        return cls(
            id=cluster_id,
            name=cluster_name or cluster_id.split("/")[-1] if "/" in cluster_id else "unknown",
            type=getattr(obj, "type", None),
            location=getattr(obj, "location", None),
            kubernetes_version=getattr(obj, "kubernetes_version", None),
            fqdn=getattr(obj, "fqdn", None),
            provisioning_state=getattr(obj, "provisioning_state", None),
            power_state=getattr(obj, "power_state", None),
            raw_data=obj.as_dict() if hasattr(obj, "as_dict") and callable(obj.as_dict) else None,  # type: ignore[attr-defined]
        )
