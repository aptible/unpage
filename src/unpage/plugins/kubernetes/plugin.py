import anyio
import kr8s.asyncio

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


class KubernetesPlugin(Plugin, KnowledgeGraphMixin):
    async def validate_plugin_config(self) -> None:
        await super().validate_plugin_config()
        await kr8s.asyncio.version()

    async def populate_graph(self, graph: Graph) -> None:
        await kr8s.asyncio.version()
        print("Populating Kubernetes graph")
        async with anyio.create_task_group() as tg:
            tg.start_soon(self._populate_namespaces, graph)
            tg.start_soon(self._populate_pods, graph)
            tg.start_soon(self._populate_services, graph)
            tg.start_soon(self._populate_deployments, graph)
            tg.start_soon(self._populate_replicasets, graph)
            tg.start_soon(self._populate_statefulsets, graph)
            tg.start_soon(self._populate_jobs, graph)
            tg.start_soon(self._populate_cronjobs, graph)
            tg.start_soon(self._populate_nodes, graph)

    async def _populate_namespaces(self, graph: Graph) -> None:
        async for namespace in kr8s.asyncio.get("namespaces"):
            await graph.add_node(
                KubernetesNamespace(
                    node_id=namespace.metadata.name,
                    raw_data=namespace.to_dict(),
                    _graph=graph,
                )
            )

    async def _populate_pods(self, graph: Graph) -> None:
        async for pod in kr8s.asyncio.get("pods"):
            await graph.add_node(
                KubernetesPod(
                    node_id=pod.metadata.name,
                    raw_data=pod.to_dict(),
                    _graph=graph,
                )
            )

    async def _populate_services(self, graph: Graph) -> None:
        async for service in kr8s.asyncio.get("services"):
            await graph.add_node(
                KubernetesService(
                    node_id=service.metadata.name,
                    raw_data=service.to_dict(),
                    _graph=graph,
                )
            )

    async def _populate_deployments(self, graph: Graph) -> None:
        async for deployment in kr8s.asyncio.get("deployments"):
            await graph.add_node(
                KubernetesDeployment(
                    node_id=deployment.metadata.name,
                    raw_data=deployment.to_dict(),
                    _graph=graph,
                )
            )

    async def _populate_replicasets(self, graph: Graph) -> None:
        async for replicaset in kr8s.asyncio.get("replicasets"):
            await graph.add_node(
                KubernetesReplicaSet(
                    node_id=replicaset.metadata.name,
                    raw_data=replicaset.to_dict(),
                    _graph=graph,
                )
            )

    async def _populate_statefulsets(self, graph: Graph) -> None:
        async for statefulset in kr8s.asyncio.get("statefulsets"):
            await graph.add_node(
                KubernetesStatefulSet(
                    node_id=statefulset.metadata.name,
                    raw_data=statefulset.to_dict(),
                    _graph=graph,
                )
            )

    async def _populate_jobs(self, graph: Graph) -> None:
        async for job in kr8s.asyncio.get("jobs"):
            await graph.add_node(
                KubernetesJob(
                    node_id=job.metadata.name,
                    raw_data=job.to_dict(),
                    _graph=graph,
                )
            )

    async def _populate_cronjobs(self, graph: Graph) -> None:
        async for cronjob in kr8s.asyncio.get("cronjobs"):
            await graph.add_node(
                KubernetesCronJob(
                    node_id=cronjob.metadata.name,
                    raw_data=cronjob.to_dict(),
                    _graph=graph,
                )
            )

    async def _populate_nodes(self, graph: Graph) -> None:
        async for pod in kr8s.asyncio.get("nodes"):
            await graph.add_node(
                KubernetesNode(
                    node_id=pod.metadata.name,
                    raw_data=pod.to_dict(),
                    _graph=graph,
                )
            )
