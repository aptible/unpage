import anyio
import typer

from unpage.cli._app import app
from unpage.cli.options import PROFILE_OPTION
from unpage.config.utils import get_config_dir
from unpage.knowledge import Graph
from unpage.telemetry import client as telemetry


@app.command()
def visualize(
    profile: str = PROFILE_OPTION,
    topology: bool = typer.Option(False, "--topology"),
) -> None:
    """Visualize the knowledge graph topology"""

    async def _visualize() -> None:
        await telemetry.send_event(
            {
                "command": "visualize_graph",
                "profile": profile,
                "topology_only": topology,
            }
        )

        graph = Graph(get_config_dir(profile) / "graph.json")

        if topology:
            graph = await graph.get_topology()

        print(await graph.to_pydot())

    anyio.run(_visualize)
