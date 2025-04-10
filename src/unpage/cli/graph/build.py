import os
import subprocess
import sys
import time
from collections import Counter

import anyio
import typer

from unpage.cli.graph._app import graph_app
from unpage.cli.graph._background import (
    check_and_create_lock,
    cleanup_pid_file,
    create_pid_file,
    get_log_file,
)
from unpage.cli.options import PROFILE_OPTION
from unpage.config import load_config
from unpage.config.utils import get_config_dir
from unpage.knowledge import Graph
from unpage.plugins import PluginManager
from unpage.plugins.mixins import KnowledgeGraphMixin
from unpage.telemetry import client as telemetry


@graph_app.command()
def build(
    profile: str = PROFILE_OPTION,
    interval: int | None = typer.Option(
        None,
        "--interval",
        help="Rebuild the graph continuously, pausing for the specified seconds between builds",
    ),
    background: bool = typer.Option(
        False, "--background", help="Run in background and return immediately"
    ),
) -> None:
    """Build a knowledge graph for your cloud infrastructure"""
    # Check if already running
    if not check_and_create_lock(profile):
        return

    if background:
        # Build command args for subprocess
        cmd = [a for a in sys.argv if a != "--background"]

        # Set up logging
        log_file = get_log_file(profile)
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # Start subprocess with logging
        with log_file.open("w") as f:
            f.write(f"Starting graph build for profile '{profile}' in background\n")
            f.write(f"Command: {' '.join(cmd)}\n")
            f.write("=" * 50 + "\n\n")
            f.flush()

            subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT, start_new_session=True)

        print(f"Graph building started in background for profile '{profile}'")
        print(f"Check progress: unpage graph logs --profile {profile} --follow")
        print(f"Stop with: unpage graph stop --profile {profile}")
        return

    # For foreground execution, also check for conflicts
    if not check_and_create_lock(profile):
        return

    async def _build_graph() -> None:
        print("Building graph...")

        start_time = time.perf_counter()

        graph = Graph()
        config = load_config(profile, create=True)
        output_path = (get_config_dir(profile) / "graph.json").resolve()
        plugin_manager = PluginManager(config)

        async with anyio.create_task_group() as tg:
            for plugin in plugin_manager.get_plugins_with_capability(KnowledgeGraphMixin):
                print(f"Populating graph with the {plugin.name} plugin...")
                tg.start_soon(plugin.populate_graph, graph)

        await graph.infer_edges()

        print(f"Saving graph to {output_path!s}...")
        await graph.save(output_path)

        end_time = time.perf_counter()
        total_time = end_time - start_time
        edge_counts = Counter(
            [edge.properties["relationship_type"] async for edge in graph.iter_edges()]
        )
        node_counts = Counter([node.node_type async for node in graph.iter_nodes()])

        print("=== Summary ===")

        print("Edges:")
        for relationship_type, count in edge_counts.items():
            print(f"  {relationship_type}: {count}")
        print("Nodes:")
        for node_type, count in node_counts.items():
            print(f"  {node_type}: {count}")

        print(f"Graph built in {total_time:.2f} seconds")
        print(f"Graph saved to {output_path!s}")
        print("=== End Summary ===")

        await telemetry.send_event(
            {
                "command": "build_graph",
                "profile": profile,
                "duration_seconds": total_time,
                "node_counts": node_counts,
                "edge_counts": edge_counts,
            }
        )

    try:
        create_pid_file(profile, os.getpid())

        if interval:
            while True:
                anyio.run(_build_graph)
                print(f"Sleeping for {interval} seconds before next build...")
                time.sleep(interval)
        else:
            anyio.run(_build_graph)
    finally:
        cleanup_pid_file(profile)
