import asyncio
from typing import Any

import rich
from azure.core.credentials import TokenCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.containerservice import ContainerServiceClient as ContainerServiceManagementClient
from azure.mgmt.cosmosdb import CosmosDBManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.rdbms.mysql import MySQLManagementClient
from azure.mgmt.rdbms.postgresql import PostgreSQLManagementClient
from azure.mgmt.sql import SqlManagementClient
from azure.mgmt.storage import StorageManagementClient
from pydantic import BaseModel, Field, ValidationError
from pydantic_core import to_jsonable_python

from unpage.config import PluginSettings
from unpage.knowledge import Graph
from unpage.plugins import Plugin
from unpage.plugins.azure.nodes.azure_aks_cluster import AzureAksCluster
from unpage.plugins.azure.nodes.azure_app_gateway import AzureAppGateway
from unpage.plugins.azure.nodes.azure_cosmos_db import AzureCosmosDb
from unpage.plugins.azure.nodes.azure_load_balancer import AzureLoadBalancer
from unpage.plugins.azure.nodes.azure_managed_disk import AzureManagedDisk
from unpage.plugins.azure.nodes.azure_mysql_database import AzureMySqlDatabase
from unpage.plugins.azure.nodes.azure_network_interface import AzureNetworkInterface
from unpage.plugins.azure.nodes.azure_network_security_group import AzureNetworkSecurityGroup
from unpage.plugins.azure.nodes.azure_postgresql_database import AzurePostgreSqlDatabase
from unpage.plugins.azure.nodes.azure_public_ip import AzurePublicIpAddress
from unpage.plugins.azure.nodes.azure_sql_database import AzureSqlDatabase
from unpage.plugins.azure.nodes.azure_storage_account import AzureStorageAccount
from unpage.plugins.azure.nodes.azure_virtual_network import AzureSubnet, AzureVirtualNetwork
from unpage.plugins.azure.nodes.azure_vm_instance import AzureVmInstance
from unpage.plugins.azure.nodes.azure_vm_scale_set import AzureVmScaleSet, AzureVmScaleSetInstance
from unpage.plugins.azure.nodes.base import DEFAULT_AZURE_SUBSCRIPTION_NAME, AzureSubscription
from unpage.plugins.azure.types import (
    AzureAksCluster as AzureAksClusterData,
)
from unpage.plugins.azure.types import (
    AzureApplicationGateway as AzureApplicationGatewayData,
)
from unpage.plugins.azure.types import (
    AzureCosmosAccount,
    AzureDatabase,
    AzureServer,
    AzureVirtualMachine,
)
from unpage.plugins.azure.types import (
    AzureLoadBalancer as AzureLoadBalancerData,
)
from unpage.plugins.azure.types import (
    AzureManagedDisk as AzureManagedDiskData,
)
from unpage.plugins.azure.types import (
    AzureNetworkInterface as AzureNetworkInterfaceData,
)
from unpage.plugins.azure.types import (
    AzureNetworkSecurityGroup as AzureNetworkSecurityGroupData,
)
from unpage.plugins.azure.types import (
    AzurePublicIpAddress as AzurePublicIpAddressData,
)
from unpage.plugins.azure.types import (
    AzureStorageAccount as AzureStorageAccountData,
)
from unpage.plugins.azure.types import (
    AzureSubnet as AzureSubnetData,
)
from unpage.plugins.azure.types import (
    AzureVirtualNetwork as AzureVirtualNetworkData,
)
from unpage.plugins.azure.types import (
    AzureVmScaleSet as AzureVmScaleSetData,
)
from unpage.plugins.azure.types import (
    AzureVmScaleSetInstance as AzureVmScaleSetInstanceData,
)
from unpage.plugins.azure.utils import (
    get_default_credential,
    handle_azure_errors,
    list_accessible_subscriptions,
    test_azure_connectivity,
)
from unpage.plugins.mixins import KnowledgeGraphMixin, McpServerMixin, tool
from unpage.utils import Choice, classproperty, print, select


class AzurePluginSettings(BaseModel):
    subscriptions: dict[str, AzureSubscription] = Field(
        default_factory=lambda: {DEFAULT_AZURE_SUBSCRIPTION_NAME: AzureSubscription()}
    )

    @property
    def subscription(self) -> AzureSubscription:
        return next(iter(self.subscriptions.values()))


class AzurePlugin(Plugin, KnowledgeGraphMixin, McpServerMixin):
    azure_settings: AzurePluginSettings
    _credential: TokenCredential | None = None

    def __init__(
        self, *args: Any, azure_settings: AzurePluginSettings | None = None, **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self.azure_settings = azure_settings if azure_settings else AzurePluginSettings()

    def init_plugin(self) -> None:
        azure_subscriptions = self._settings.get("subscriptions")
        if not azure_subscriptions:
            self.azure_settings = AzurePluginSettings()
            return
        if not isinstance(azure_subscriptions, dict):
            raise ValueError("azure subscriptions must be a dictionary in config.yaml")
        if len(azure_subscriptions) != 1:
            raise ValueError(
                "More than one Azure subscription configured in config.yaml; we only support one Azure subscription at this time. Please let us know if you need multiple subscription support."
            )
        for subscription_name, subscription_settings in azure_subscriptions.items():
            try:
                self.azure_settings = AzurePluginSettings(
                    subscriptions={
                        subscription_name: AzureSubscription(
                            **{
                                "name": subscription_name,
                                **to_jsonable_python(subscription_settings),
                            }
                        )
                    }
                )
            except ValidationError as ex:
                raise ValueError(
                    f"Invalid Azure subscription settings for subscription '{subscription_name}'. Review your config.yaml. {subscription_settings=}; error={ex!s}"
                ) from ex

    async def validate_plugin_config(self) -> None:
        await super().validate_plugin_config()
        credential = await self._get_credential()
        subscription_id = self.azure_settings.subscription.subscription_id

        if not subscription_id:
            raise ValueError("Azure subscription ID is required")

        # Test connectivity
        if not await test_azure_connectivity(credential, subscription_id):
            raise ValueError(
                f"Cannot access Azure subscription {subscription_id}. "
                "Please check your authentication and permissions."
            )

    @classproperty
    def default_plugin_settings(cls) -> PluginSettings:
        return AzurePluginSettings().model_dump()

    async def interactive_configure(self) -> PluginSettings:
        rich.print("> The Azure plugin will add resources from Azure to your infra knowledge graph")
        rich.print(
            "> You can authenticate using Azure CLI, Environment Variables, or Managed Identity"
        )
        rich.print(
            "> Make sure you have appropriate permissions to read resources in your subscription"
        )
        rich.print("")

        try:
            credential = await get_default_credential()
            subscriptions = await list_accessible_subscriptions(credential)
        except Exception as e:
            rich.print(f"[red]Error: Failed to authenticate with Azure: {e!s}[/red]")
            rich.print(
                "Please ensure you're authenticated with Azure CLI or have appropriate credentials set"
            )
            return {}

        if not subscriptions:
            rich.print("[yellow]Warning: No Azure subscriptions found or accessible[/yellow]")
            return {}

        rich.print(f"Found {len(subscriptions)} accessible Azure subscription(s)")

        # Filter to only enabled subscriptions
        enabled_subscriptions = [sub for sub in subscriptions if sub["state"] == "Enabled"]

        if not enabled_subscriptions:
            rich.print("[yellow]Warning: No enabled Azure subscriptions found[/yellow]")
            return {}

        # Select subscription
        if len(enabled_subscriptions) == 1:
            selected_subscription = enabled_subscriptions[0]
            rich.print(
                f"Using subscription: {selected_subscription['display_name']} ({selected_subscription['subscription_id']})"
            )
        else:
            choices = [
                Choice(
                    sub["subscription_id"],
                    checked=(
                        sub["subscription_id"] == self.azure_settings.subscription.subscription_id
                    ),
                )
                for sub in enabled_subscriptions
            ]
            # Add display names to choices
            for i, choice in enumerate(choices):
                choice.title = f"{enabled_subscriptions[i]['display_name']} ({choice.value})"

            checked_choices = [c for c in choices if c.checked]
            default_choice = choices[0] if not checked_choices else checked_choices[0]

            selected_subscription_id = await select(
                "Which Azure subscription would you like to use with the Unpage plugin?",
                choices=choices,
                default=default_choice,
                use_search_filter=len(choices) > 10,
                use_jk_keys=len(choices) <= 10,
            )

            selected_subscription = next(
                sub
                for sub in enabled_subscriptions
                if sub["subscription_id"] == selected_subscription_id
            )

        # Create settings
        settings = AzurePluginSettings(
            subscriptions={
                "default": AzureSubscription(
                    name="default",
                    subscription_id=selected_subscription["subscription_id"],
                    tenant_id=selected_subscription["tenant_id"],
                )
            }
        )

        # Test the configuration
        try:
            test_successful = await test_azure_connectivity(
                credential, selected_subscription["subscription_id"]
            )
            if not test_successful:
                rich.print(
                    "[yellow]Warning: Could not verify full access to the selected subscription[/yellow]"
                )
            else:
                rich.print("[green]✓ Azure configuration validated successfully[/green]")
        except Exception as e:
            rich.print(f"[yellow]Warning: Could not validate Azure configuration: {e!s}[/yellow]")

        return settings.model_dump()

    async def _get_credential(self) -> TokenCredential:
        """Get or create the Azure credential."""
        if self._credential is None:
            self._credential = await get_default_credential()
        return self._credential

    def _validate_subscription(self, subscription: AzureSubscription, operation: str) -> str:
        """Validate subscription has required ID and return it."""
        if not subscription.subscription_id:
            print(f"Skipping {operation}: no subscription ID configured")
            raise ValueError(f"Subscription ID required for {operation}")
        return subscription.subscription_id

    async def populate_graph(self, graph: Graph) -> None:
        credential = await self._get_credential()
        subscription = self.azure_settings.subscription

        # Populate all resource types in parallel
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self.populate_vm_instances(graph, credential, subscription))
            tg.create_task(self.populate_vm_scale_sets(graph, credential, subscription))
            tg.create_task(self.populate_sql_databases(graph, credential, subscription))
            tg.create_task(self.populate_postgresql_databases(graph, credential, subscription))
            tg.create_task(self.populate_mysql_databases(graph, credential, subscription))
            tg.create_task(self.populate_cosmos_databases(graph, credential, subscription))
            tg.create_task(self.populate_load_balancers(graph, credential, subscription))
            tg.create_task(self.populate_application_gateways(graph, credential, subscription))
            tg.create_task(self.populate_managed_disks(graph, credential, subscription))
            tg.create_task(self.populate_storage_accounts(graph, credential, subscription))
            tg.create_task(self.populate_public_ips(graph, credential, subscription))
            tg.create_task(self.populate_virtual_networks(graph, credential, subscription))
            tg.create_task(self.populate_network_security_groups(graph, credential, subscription))
            tg.create_task(self.populate_network_interfaces(graph, credential, subscription))
            tg.create_task(self.populate_aks_clusters(graph, credential, subscription))

    async def populate_vm_instances(
        self, graph: Graph, credential: TokenCredential, subscription: AzureSubscription
    ) -> None:
        print("Populating Azure VM instances")
        vm_count = 0

        subscription_id = self._validate_subscription(subscription, "VM instance population")

        async with handle_azure_errors("Compute", "populate VM instances"):
            client = ComputeManagementClient(credential, subscription_id)

            # Use asyncio.to_thread to make the sync call async
            vm_list = await asyncio.to_thread(client.virtual_machines.list_all)

            for vm_obj in vm_list:
                vm_data = AzureVirtualMachine.from_sdk_object(vm_obj)
                if vm_data:
                    await graph.add_node(
                        AzureVmInstance(
                            node_id=vm_data.id,
                            raw_data=vm_data.raw_data or {},
                            _graph=graph,
                            azure_subscription=subscription,
                            credential=credential,
                        )
                    )
                    vm_count += 1

        print(f"Initialized {vm_count} Azure VM instances")

    async def populate_sql_databases(
        self, graph: Graph, credential: TokenCredential, subscription: AzureSubscription
    ) -> None:
        print("Populating Azure SQL databases")
        db_count = 0

        subscription_id = self._validate_subscription(subscription, "SQL database population")

        async with handle_azure_errors("SQL", "populate SQL databases"):
            client = SqlManagementClient(credential, subscription_id)

            # Get all SQL servers first
            servers = await asyncio.to_thread(client.servers.list)

            for server_obj in servers:
                server_data = AzureServer.from_sdk_object(server_obj)
                if not server_data or not server_data.resource_group:
                    continue

                # Get databases for each server
                databases = await asyncio.to_thread(
                    client.databases.list_by_server,
                    resource_group_name=server_data.resource_group,
                    server_name=server_data.name,
                )

                for db_obj in databases:
                    db_data = AzureDatabase.from_sdk_object(db_obj)
                    # Skip master database and ensure we have valid data
                    if db_data and db_data.name.lower() != "master":
                        await graph.add_node(
                            AzureSqlDatabase(
                                node_id=db_data.id,
                                raw_data=db_data.raw_data or {},
                                _graph=graph,
                                azure_subscription=subscription,
                                credential=credential,
                            )
                        )
                        db_count += 1

        print(f"Initialized {db_count} Azure SQL databases")

    async def populate_postgresql_databases(
        self, graph: Graph, credential: TokenCredential, subscription: AzureSubscription
    ) -> None:
        print("Populating Azure PostgreSQL databases")
        db_count = 0

        subscription_id = self._validate_subscription(
            subscription, "PostgreSQL database population"
        )

        async with handle_azure_errors("PostgreSQL", "populate PostgreSQL databases"):
            client = PostgreSQLManagementClient(credential, subscription_id)

            # Get all PostgreSQL servers
            servers = await asyncio.to_thread(client.servers.list)

            for server_obj in servers:
                server_data = AzureServer.from_sdk_object(server_obj)
                if not server_data or not server_data.resource_group:
                    continue

                # Get databases for each server
                databases = await asyncio.to_thread(
                    client.databases.list_by_server,
                    resource_group_name=server_data.resource_group,
                    server_name=server_data.name,
                )

                for db_obj in databases:
                    db_data = AzureDatabase.from_sdk_object(db_obj)
                    if db_data:
                        await graph.add_node(
                            AzurePostgreSqlDatabase(
                                node_id=db_data.id,
                                raw_data=db_data.raw_data or {},
                                _graph=graph,
                                azure_subscription=subscription,
                                credential=credential,
                            )
                        )
                        db_count += 1

        print(f"Initialized {db_count} Azure PostgreSQL databases")

    async def populate_mysql_databases(
        self, graph: Graph, credential: TokenCredential, subscription: AzureSubscription
    ) -> None:
        print("Populating Azure MySQL databases")
        db_count = 0

        subscription_id = self._validate_subscription(subscription, "MySQL database population")

        async with handle_azure_errors("MySQL", "populate MySQL databases"):
            client = MySQLManagementClient(credential, subscription_id)

            servers = await asyncio.to_thread(client.servers.list)

            for server_obj in servers:
                server_data = AzureServer.from_sdk_object(server_obj)
                if not server_data or not server_data.resource_group:
                    continue

                databases = await asyncio.to_thread(
                    client.databases.list_by_server,
                    resource_group_name=server_data.resource_group,
                    server_name=server_data.name,
                )

                for db_obj in databases:
                    db_data = AzureDatabase.from_sdk_object(db_obj)
                    if db_data:
                        await graph.add_node(
                            AzureMySqlDatabase(
                                node_id=db_data.id,
                                raw_data=db_data.raw_data or {},
                                _graph=graph,
                                azure_subscription=subscription,
                                credential=credential,
                            )
                        )
                        db_count += 1

        print(f"Initialized {db_count} Azure MySQL databases")

    async def populate_cosmos_databases(
        self, graph: Graph, credential: TokenCredential, subscription: AzureSubscription
    ) -> None:
        print("Populating Azure Cosmos DB accounts")
        db_count = 0

        subscription_id = self._validate_subscription(subscription, "Cosmos DB population")

        async with handle_azure_errors("CosmosDB", "populate Cosmos DB accounts"):
            client = CosmosDBManagementClient(credential, subscription_id)

            accounts = await asyncio.to_thread(client.database_accounts.list)

            for account_obj in accounts:
                account_data = AzureCosmosAccount.from_sdk_object(account_obj)
                if account_data:
                    await graph.add_node(
                        AzureCosmosDb(
                            node_id=account_data.id,
                            raw_data=account_data.raw_data or {},
                            _graph=graph,
                            azure_subscription=subscription,
                            credential=credential,
                        )
                    )
                    db_count += 1

        print(f"Initialized {db_count} Azure Cosmos DB accounts")

    async def populate_load_balancers(
        self, graph: Graph, credential: TokenCredential, subscription: AzureSubscription
    ) -> None:
        print("Populating Azure Load Balancers")
        lb_count = 0

        subscription_id = self._validate_subscription(subscription, "Load Balancer population")

        async with handle_azure_errors("Network", "populate Load Balancers"):
            client = NetworkManagementClient(credential, subscription_id)

            load_balancers = await asyncio.to_thread(client.load_balancers.list_all)

            for lb_obj in load_balancers:
                lb_data = AzureLoadBalancerData.from_sdk_object(lb_obj)
                if lb_data:
                    await graph.add_node(
                        AzureLoadBalancer(
                            node_id=lb_data.id,
                            raw_data=lb_data.raw_data or {},
                            _graph=graph,
                            azure_subscription=subscription,
                            credential=credential,
                        )
                    )
                    lb_count += 1

        print(f"Initialized {lb_count} Azure Load Balancers")

    async def populate_application_gateways(
        self, graph: Graph, credential: TokenCredential, subscription: AzureSubscription
    ) -> None:
        print("Populating Azure Application Gateways")
        ag_count = 0

        subscription_id = self._validate_subscription(
            subscription, "Application Gateway population"
        )

        async with handle_azure_errors("Network", "populate Application Gateways"):
            client = NetworkManagementClient(credential, subscription_id)

            app_gateways = await asyncio.to_thread(client.application_gateways.list_all)

            for ag_obj in app_gateways:
                ag_data = AzureApplicationGatewayData.from_sdk_object(ag_obj)
                if ag_data:
                    await graph.add_node(
                        AzureAppGateway(
                            node_id=ag_data.id,
                            raw_data=ag_data.raw_data or {},
                            _graph=graph,
                            azure_subscription=subscription,
                            credential=credential,
                        )
                    )
                    ag_count += 1

        print(f"Initialized {ag_count} Azure Application Gateways")

    async def populate_managed_disks(
        self, graph: Graph, credential: TokenCredential, subscription: AzureSubscription
    ) -> None:
        print("Populating Azure Managed Disks")
        disk_count = 0

        subscription_id = self._validate_subscription(subscription, "Managed Disk population")

        async with handle_azure_errors("Compute", "populate Managed Disks"):
            client = ComputeManagementClient(credential, subscription_id)

            disks = await asyncio.to_thread(client.disks.list)

            for disk_obj in disks:
                disk_data = AzureManagedDiskData.from_sdk_object(disk_obj)
                if disk_data:
                    await graph.add_node(
                        AzureManagedDisk(
                            node_id=disk_data.id,
                            raw_data=disk_data.raw_data or {},
                            _graph=graph,
                            azure_subscription=subscription,
                            credential=credential,
                        )
                    )
                    disk_count += 1

        print(f"Initialized {disk_count} Azure Managed Disks")

    async def populate_storage_accounts(
        self, graph: Graph, credential: TokenCredential, subscription: AzureSubscription
    ) -> None:
        print("Populating Azure Storage Accounts")
        storage_count = 0

        subscription_id = self._validate_subscription(subscription, "Storage Account population")

        async with handle_azure_errors("Storage", "populate Storage Accounts"):
            client = StorageManagementClient(credential, subscription_id)

            storage_accounts = await asyncio.to_thread(client.storage_accounts.list)

            for storage_obj in storage_accounts:
                storage_data = AzureStorageAccountData.from_sdk_object(storage_obj)
                if storage_data:
                    await graph.add_node(
                        AzureStorageAccount(
                            node_id=storage_data.id,
                            raw_data=storage_data.raw_data or {},
                            _graph=graph,
                            azure_subscription=subscription,
                            credential=credential,
                        )
                    )
                    storage_count += 1

        print(f"Initialized {storage_count} Azure Storage Accounts")

    async def populate_vm_scale_sets(
        self, graph: Graph, credential: TokenCredential, subscription: AzureSubscription
    ) -> None:
        print("Populating Azure VM Scale Sets")
        vmss_count = 0
        instance_count = 0

        subscription_id = self._validate_subscription(subscription, "VM Scale Set population")

        async with handle_azure_errors("Compute", "populate VM Scale Sets"):
            client = ComputeManagementClient(credential, subscription_id)

            # Get all VM Scale Sets
            scale_sets = await asyncio.to_thread(client.virtual_machine_scale_sets.list_all)

            for vmss_obj in scale_sets:
                vmss_data = AzureVmScaleSetData.from_sdk_object(vmss_obj)
                if vmss_data:
                    await graph.add_node(
                        AzureVmScaleSet(
                            node_id=vmss_data.id,
                            raw_data=vmss_data.raw_data or {},
                            _graph=graph,
                            azure_subscription=subscription,
                            credential=credential,
                        )
                    )
                    vmss_count += 1

                    # Get instances for each scale set
                    resource_group = vmss_data.id.split("/")[4] if "/" in vmss_data.id else None
                    if resource_group:
                        try:
                            instances = await asyncio.to_thread(
                                client.virtual_machine_scale_set_vms.list,
                                resource_group_name=resource_group,
                                virtual_machine_scale_set_name=vmss_data.name,
                            )

                            for instance_obj in instances:
                                instance_data = AzureVmScaleSetInstanceData.from_sdk_object(
                                    instance_obj
                                )
                                if instance_data:
                                    await graph.add_node(
                                        AzureVmScaleSetInstance(
                                            node_id=instance_data.id,
                                            raw_data=instance_data.raw_data or {},
                                            _graph=graph,
                                            azure_subscription=subscription,
                                            credential=credential,
                                        )
                                    )
                                    instance_count += 1
                        except Exception as e:
                            print(f"Error getting instances for {vmss_data.name}: {e}")

        print(f"Initialized {vmss_count} Azure VM Scale Sets and {instance_count} instances")

    async def populate_public_ips(
        self, graph: Graph, credential: TokenCredential, subscription: AzureSubscription
    ) -> None:
        print("Populating Azure Public IP Addresses")
        ip_count = 0

        subscription_id = self._validate_subscription(subscription, "Public IP population")

        async with handle_azure_errors("Network", "populate Public IP Addresses"):
            client = NetworkManagementClient(credential, subscription_id)

            public_ips = await asyncio.to_thread(client.public_ip_addresses.list_all)

            for ip_obj in public_ips:
                ip_data = AzurePublicIpAddressData.from_sdk_object(ip_obj)
                if ip_data:
                    await graph.add_node(
                        AzurePublicIpAddress(
                            node_id=ip_data.id,
                            raw_data=ip_data.raw_data or {},
                            _graph=graph,
                            azure_subscription=subscription,
                            credential=credential,
                        )
                    )
                    ip_count += 1

        print(f"Initialized {ip_count} Azure Public IP Addresses")

    async def populate_virtual_networks(
        self, graph: Graph, credential: TokenCredential, subscription: AzureSubscription
    ) -> None:
        print("Populating Azure Virtual Networks and Subnets")
        vnet_count = 0
        subnet_count = 0

        subscription_id = self._validate_subscription(subscription, "Virtual Network population")

        async with handle_azure_errors("Network", "populate Virtual Networks"):
            client = NetworkManagementClient(credential, subscription_id)

            vnets = await asyncio.to_thread(client.virtual_networks.list_all)

            for vnet_obj in vnets:
                vnet_data = AzureVirtualNetworkData.from_sdk_object(vnet_obj)
                if vnet_data:
                    await graph.add_node(
                        AzureVirtualNetwork(
                            node_id=vnet_data.id,
                            raw_data=vnet_data.raw_data or {},
                            _graph=graph,
                            azure_subscription=subscription,
                            credential=credential,
                        )
                    )
                    vnet_count += 1

                    # Get subnets for each VNet
                    resource_group = vnet_data.id.split("/")[4] if "/" in vnet_data.id else None
                    if resource_group:
                        try:
                            subnets = await asyncio.to_thread(
                                client.subnets.list,
                                resource_group_name=resource_group,
                                virtual_network_name=vnet_data.name,
                            )

                            for subnet_obj in subnets:
                                subnet_data = AzureSubnetData.from_sdk_object(subnet_obj)
                                if subnet_data:
                                    await graph.add_node(
                                        AzureSubnet(
                                            node_id=subnet_data.id,
                                            raw_data=subnet_data.raw_data or {},
                                            _graph=graph,
                                            azure_subscription=subscription,
                                            credential=credential,
                                        )
                                    )
                                    subnet_count += 1
                        except Exception as e:
                            print(f"Error getting subnets for {vnet_data.name}: {e}")

        print(f"Initialized {vnet_count} Azure Virtual Networks and {subnet_count} Subnets")

    async def populate_network_security_groups(
        self, graph: Graph, credential: TokenCredential, subscription: AzureSubscription
    ) -> None:
        print("Populating Azure Network Security Groups")
        nsg_count = 0

        subscription_id = self._validate_subscription(subscription, "NSG population")

        async with handle_azure_errors("Network", "populate Network Security Groups"):
            client = NetworkManagementClient(credential, subscription_id)

            nsgs = await asyncio.to_thread(client.network_security_groups.list_all)

            for nsg_obj in nsgs:
                nsg_data = AzureNetworkSecurityGroupData.from_sdk_object(nsg_obj)
                if nsg_data:
                    await graph.add_node(
                        AzureNetworkSecurityGroup(
                            node_id=nsg_data.id,
                            raw_data=nsg_data.raw_data or {},
                            _graph=graph,
                            azure_subscription=subscription,
                            credential=credential,
                        )
                    )
                    nsg_count += 1

        print(f"Initialized {nsg_count} Azure Network Security Groups")

    async def populate_network_interfaces(
        self, graph: Graph, credential: TokenCredential, subscription: AzureSubscription
    ) -> None:
        print("Populating Azure Network Interfaces")
        nic_count = 0

        subscription_id = self._validate_subscription(subscription, "Network Interface population")

        async with handle_azure_errors("Network", "populate Network Interfaces"):
            client = NetworkManagementClient(credential, subscription_id)

            nics = await asyncio.to_thread(client.network_interfaces.list_all)

            for nic_obj in nics:
                nic_data = AzureNetworkInterfaceData.from_sdk_object(nic_obj)
                if nic_data:
                    await graph.add_node(
                        AzureNetworkInterface(
                            node_id=nic_data.id,
                            raw_data=nic_data.raw_data or {},
                            _graph=graph,
                            azure_subscription=subscription,
                            credential=credential,
                        )
                    )
                    nic_count += 1

        print(f"Initialized {nic_count} Azure Network Interfaces")

    async def populate_aks_clusters(
        self, graph: Graph, credential: TokenCredential, subscription: AzureSubscription
    ) -> None:
        print("Populating Azure AKS Clusters")
        cluster_count = 0

        subscription_id = self._validate_subscription(subscription, "AKS Cluster population")

        async with handle_azure_errors("ContainerService", "populate AKS Clusters"):
            client = ContainerServiceManagementClient(credential, subscription_id)

            clusters = await asyncio.to_thread(client.managed_clusters.list)

            for cluster_obj in clusters:
                cluster_data = AzureAksClusterData.from_sdk_object(cluster_obj)
                if cluster_data:
                    await graph.add_node(
                        AzureAksCluster(
                            node_id=cluster_data.id,
                            raw_data=cluster_data.raw_data or {},
                            _graph=graph,
                            azure_subscription=subscription,
                            credential=credential,
                        )
                    )
                    cluster_count += 1

        print(f"Initialized {cluster_count} Azure AKS Clusters")

    @tool()
    async def get_realtime_vm_status(self, vm_name: str, resource_group: str) -> dict | str:
        """
        Get real-time status information for an Azure VM instance directly from Azure API.

        Args:
            vm_name: Azure VM name
            resource_group: Azure resource group name

        Returns:
            dict containing current VM power state and status details
        """
        try:
            credential = await self._get_credential()
            subscription_id = self.azure_settings.subscription.subscription_id
            if not subscription_id:
                return "Error: Azure subscription ID not configured"

            client = ComputeManagementClient(credential, subscription_id)

            # Get VM instance view
            instance_view = await asyncio.to_thread(
                client.virtual_machines.instance_view,
                resource_group_name=resource_group,
                vm_name=vm_name,
            )

            # Extract status information safely
            statuses = getattr(instance_view, "statuses", [])
            power_state = "Unknown"
            provisioning_state = "Unknown"
            status_list = []

            for status in statuses:
                code = getattr(status, "code", "")
                display_status = getattr(status, "display_status", "")

                if code.startswith("PowerState/"):
                    power_state = display_status
                elif code.startswith("ProvisioningState/"):
                    provisioning_state = display_status

                status_list.append({"code": code, "display_status": display_status})

            return {
                "vm_name": vm_name,
                "resource_group": resource_group,
                "power_state": power_state,
                "provisioning_state": provisioning_state,
                "statuses": status_list,
            }

        except Exception as e:
            return f"Error retrieving VM status: {e!s}"

    @tool()
    async def get_sql_database_status(
        self, database_name: str, server_name: str, resource_group: str
    ) -> dict | str:
        """
        Get status information for an Azure SQL database.

        Args:
            database_name: Azure SQL database name
            server_name: Azure SQL server name
            resource_group: Azure resource group name

        Returns:
            dict containing database status and configuration details
        """
        try:
            credential = await self._get_credential()
            subscription_id = self.azure_settings.subscription.subscription_id
            if not subscription_id:
                return "Error: Azure subscription ID not configured"

            client = SqlManagementClient(credential, subscription_id)

            # Get database details
            database_obj = await asyncio.to_thread(
                client.databases.get,
                resource_group_name=resource_group,
                server_name=server_name,
                database_name=database_name,
            )

            # Convert to type-safe data class
            database_data = AzureDatabase.from_sdk_object(database_obj)
            if not database_data:
                return f"Error: Could not retrieve database {database_name}"

            return {
                "database_name": database_name,
                "server_name": server_name,
                "resource_group": resource_group,
                "status": database_data.status,
                "edition": database_data.edition,
                "service_level_objective": database_data.service_level_objective,
                "collation": database_data.collation,
                "max_size_bytes": database_data.max_size_bytes,
                "creation_date": database_data.creation_date,
            }

        except Exception as e:
            return f"Error retrieving SQL database status: {e!s}"
