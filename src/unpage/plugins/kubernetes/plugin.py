import asyncio
from typing import TYPE_CHECKING, Any

import anyio
import kr8s
import kr8s.asyncio
import rich
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from kr8s._api import Api

from unpage.config import PluginSettings
from unpage.knowledge.graph import Graph
from unpage.plugins import Plugin
from unpage.plugins.kubernetes.nodes.kubernetes_cron_job import KubernetesCronJob
from unpage.plugins.kubernetes.nodes.kubernetes_deployment import KubernetesDeployment
from unpage.plugins.kubernetes.nodes.kubernetes_job import KubernetesJob
from unpage.plugins.kubernetes.nodes.kubernetes_namespace import KubernetesNamespace
from unpage.plugins.kubernetes.nodes.kubernetes_node import KubernetesNode
from unpage.plugins.kubernetes.nodes.kubernetes_pod import KubernetesPod
from unpage.plugins.kubernetes.nodes.kubernetes_replica_set import KubernetesReplicaSet
from unpage.plugins.kubernetes.nodes.kubernetes_service import KubernetesService
from unpage.plugins.kubernetes.nodes.kubernetes_stateful_set import KubernetesStatefulSet
from unpage.plugins.mixins.graph import KnowledgeGraphMixin
from unpage.utils import Choice, checkbox, classproperty, select


class KubernetesContext(BaseModel):
    """Configuration for a Kubernetes context."""

    name: str
    kubeconfig: str | None = None  # Optional custom kubeconfig path


class KubernetesPluginSettings(BaseModel):
    """Settings for the Kubernetes plugin."""

    contexts: list[KubernetesContext] = Field(default_factory=list)
    include_all_contexts: bool = False
    kubeconfig_path: str | None = None  # Global kubeconfig path


class KubernetesPlugin(Plugin, KnowledgeGraphMixin):
    kubernetes_settings: KubernetesPluginSettings

    def __init__(
        self, *args: Any, kubernetes_settings: KubernetesPluginSettings | None = None, **kwargs: Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self.kubernetes_settings = (
            kubernetes_settings if kubernetes_settings else KubernetesPluginSettings()
        )

    def init_plugin(self) -> None:
        """Initialize plugin with settings from config."""
        settings = self._settings
        if not settings:
            self.kubernetes_settings = KubernetesPluginSettings()
            return

        # Parse settings from config
        contexts = []
        context_settings = settings.get("contexts", [])

        # Handle list of context names or dict of context configs
        if isinstance(context_settings, list):
            for ctx in context_settings:
                if isinstance(ctx, str):
                    contexts.append(KubernetesContext(name=ctx))
                elif isinstance(ctx, dict):
                    contexts.append(KubernetesContext(**ctx))
        elif isinstance(context_settings, dict):
            for name, config in context_settings.items():
                if isinstance(config, dict):
                    contexts.append(KubernetesContext(name=name, **config))
                else:
                    contexts.append(KubernetesContext(name=name))

        self.kubernetes_settings = KubernetesPluginSettings(
            contexts=contexts,
            include_all_contexts=settings.get("include_all_contexts", False),
            kubeconfig_path=settings.get("kubeconfig_path"),
        )

    @classproperty
    def default_plugin_settings(cls) -> PluginSettings:
        return KubernetesPluginSettings().model_dump()

    async def interactive_configure(self) -> PluginSettings:
        """Interactive configuration for Kubernetes contexts."""
        rich.print(
            "> The Kubernetes plugin will add resources from Kubernetes clusters to your knowledge graph"
        )
        rich.print("> You can select specific contexts or include all available contexts")
        rich.print("")

        # Get available contexts
        try:
            # Run kubectl to get contexts
            result = await asyncio.create_subprocess_shell(
                "kubectl config get-contexts -o name",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await result.communicate()
            available_contexts = stdout.decode().strip().split("\n") if stdout else []
        except Exception:
            available_contexts = []

        if not available_contexts:
            rich.print("[yellow]No Kubernetes contexts found[/yellow]")
            return {}

        rich.print(f"Found {len(available_contexts)} Kubernetes context(s)")

        # Ask if user wants all contexts or specific ones
        include_all_choice = await select(
            "How would you like to configure Kubernetes contexts?",
            choices=[
                Choice("Select specific contexts", value=False),
                Choice("Include all available contexts", value=True),
            ],
            default=Choice("Select specific contexts", value=False),
        )

        # Extract the value from the Choice object
        include_all = (
            include_all_choice.value
            if isinstance(include_all_choice, Choice)
            else include_all_choice
        )

        contexts = []
        if include_all:
            contexts = [KubernetesContext(name=ctx) for ctx in available_contexts]
            rich.print(f"[green]✓ Will include all {len(contexts)} contexts[/green]")
        else:
            # Let user select specific contexts
            selected_choices = await checkbox(
                "Select Kubernetes contexts to include:",
                choices=[Choice(ctx, value=ctx) for ctx in available_contexts],
            )
            # Extract values from Choice objects
            selected = [
                choice.value if isinstance(choice, Choice) else choice
                for choice in selected_choices
            ]
            contexts = [KubernetesContext(name=ctx) for ctx in selected if ctx]
            rich.print(f"[green]✓ Selected {len(contexts)} context(s)[/green]")

        settings = KubernetesPluginSettings(
            contexts=contexts,
            include_all_contexts=bool(include_all),
        )

        return settings.model_dump()

    async def validate_plugin_config(self) -> None:
        await super().validate_plugin_config()
        await kr8s.asyncio.version()

    async def populate_graph(self, graph: Graph) -> None:
        """Populate the graph with Kubernetes resources from configured contexts."""
        print("Populating Kubernetes graph")

        # Determine which contexts to use
        contexts_to_use = await self._get_contexts_to_use()

        if not contexts_to_use:
            # Fallback to current context if no configuration
            print("Using current Kubernetes context")
            try:
                # Create API client for default context
                api = await kr8s.asyncio.api()
                await api.version()
                await self._populate_context(graph, api, "")
            except Exception as e:
                print(f"Warning: Could not connect to default context: {e}")
        else:
            # Populate from each configured context
            for context in contexts_to_use:
                print(f"Populating from Kubernetes context: {context}")
                try:
                    # Create API client for specific context
                    api = await kr8s.asyncio.api(
                        context=context,
                        kubeconfig=self.kubernetes_settings.kubeconfig_path,
                    )
                    # Verify connection
                    await api.version()
                    # Populate with context prefix
                    await self._populate_context(graph, api, f"{context}:")
                except Exception as e:
                    import traceback

                    print(f"Warning: Could not connect to context '{context}': {e}")
                    print(f"Traceback: {traceback.format_exc()}")

    async def _get_contexts_to_use(self) -> list[str]:
        """Get the list of contexts to use based on configuration."""
        if self.kubernetes_settings.include_all_contexts:
            # Get all available contexts
            try:
                result = await asyncio.create_subprocess_shell(
                    "kubectl config get-contexts -o name",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await result.communicate()
                return stdout.decode().strip().split("\n") if stdout else []
            except Exception:
                return []
        elif self.kubernetes_settings.contexts:
            # Use configured contexts
            return [ctx.name for ctx in self.kubernetes_settings.contexts]
        else:
            # No configuration, use default behavior
            return []

    async def _populate_context(self, graph: Graph, api: "Api", context_prefix: str) -> None:
        """Populate resources from a specific context."""
        async with anyio.create_task_group() as tg:
            tg.start_soon(self._populate_namespaces, graph, api, context_prefix)
            tg.start_soon(self._populate_pods, graph, api, context_prefix)
            tg.start_soon(self._populate_services, graph, api, context_prefix)
            tg.start_soon(self._populate_deployments, graph, api, context_prefix)
            tg.start_soon(self._populate_replicasets, graph, api, context_prefix)
            tg.start_soon(self._populate_statefulsets, graph, api, context_prefix)
            tg.start_soon(self._populate_jobs, graph, api, context_prefix)
            tg.start_soon(self._populate_cronjobs, graph, api, context_prefix)
            tg.start_soon(self._populate_nodes, graph, api, context_prefix)

    async def _populate_namespaces(self, graph: Graph, api: "Api", context_prefix: str) -> None:
        async for namespace in api.get("namespaces"):
            await graph.add_node(
                KubernetesNamespace(
                    node_id=f"{context_prefix}{namespace.metadata.name}",
                    raw_data=namespace.to_dict(),
                    _graph=graph,
                )
            )

    async def _populate_pods(self, graph: Graph, api: "Api", context_prefix: str) -> None:
        async for pod in api.get("pods"):
            await graph.add_node(
                KubernetesPod(
                    node_id=f"{context_prefix}{pod.metadata.name}",
                    raw_data=pod.to_dict(),
                    _graph=graph,
                )
            )

    async def _populate_services(self, graph: Graph, api: "Api", context_prefix: str) -> None:
        async for service in api.get("services"):
            await graph.add_node(
                KubernetesService(
                    node_id=f"{context_prefix}{service.metadata.name}",
                    raw_data=service.to_dict(),
                    _graph=graph,
                )
            )

    async def _populate_deployments(self, graph: Graph, api: "Api", context_prefix: str) -> None:
        async for deployment in api.get("deployments"):
            await graph.add_node(
                KubernetesDeployment(
                    node_id=f"{context_prefix}{deployment.metadata.name}",
                    raw_data=deployment.to_dict(),
                    _graph=graph,
                )
            )

    async def _populate_replicasets(self, graph: Graph, api: "Api", context_prefix: str) -> None:
        async for replicaset in api.get("replicasets"):
            await graph.add_node(
                KubernetesReplicaSet(
                    node_id=f"{context_prefix}{replicaset.metadata.name}",
                    raw_data=replicaset.to_dict(),
                    _graph=graph,
                )
            )

    async def _populate_statefulsets(self, graph: Graph, api: "Api", context_prefix: str) -> None:
        async for statefulset in api.get("statefulsets"):
            await graph.add_node(
                KubernetesStatefulSet(
                    node_id=f"{context_prefix}{statefulset.metadata.name}",
                    raw_data=statefulset.to_dict(),
                    _graph=graph,
                )
            )

    async def _populate_jobs(self, graph: Graph, api: "Api", context_prefix: str) -> None:
        async for job in api.get("jobs"):
            await graph.add_node(
                KubernetesJob(
                    node_id=f"{context_prefix}{job.metadata.name}",
                    raw_data=job.to_dict(),
                    _graph=graph,
                )
            )

    async def _populate_cronjobs(self, graph: Graph, api: "Api", context_prefix: str) -> None:
        async for cronjob in api.get("cronjobs"):
            await graph.add_node(
                KubernetesCronJob(
                    node_id=f"{context_prefix}{cronjob.metadata.name}",
                    raw_data=cronjob.to_dict(),
                    _graph=graph,
                )
            )

    async def _populate_nodes(self, graph: Graph, api: "Api", context_prefix: str) -> None:
        async for node in api.get("nodes"):
            await graph.add_node(
                KubernetesNode(
                    node_id=f"{context_prefix}{node.metadata.name}",
                    raw_data=node.to_dict(),
                    _graph=graph,
                )
            )
