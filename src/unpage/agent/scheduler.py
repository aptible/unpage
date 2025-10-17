"""Scheduler service for running agents on a periodic schedule."""

import asyncio
import signal
import sys
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from rich import print

from unpage.agent.analysis import Agent, AnalysisAgent
from unpage.agent.utils import get_agents, load_agent


class AgentScheduler:
    """Scheduler for running agents on a periodic schedule."""

    def __init__(self) -> None:
        """Initialize the agent scheduler."""
        self.scheduler = AsyncIOScheduler(timezone=UTC)
        self.scheduled_agents: dict[str, Agent] = {}
        self.shutdown_event = asyncio.Event()

    def load_scheduled_agents(self) -> None:
        """Load all agents that have a schedule configured."""
        agent_names = get_agents()

        for agent_name in agent_names:
            try:
                agent = load_agent(agent_name)

                if agent.schedule:
                    self.scheduled_agents[agent.name] = agent
                    print(f"[green]Loaded scheduled agent:[/green] {agent.name}")
                    print(f"  - Schedule: {agent.schedule.cron}")
                    print(f"  - Description: {agent.description}")
            except Exception as ex:
                print(f"[red]Failed to load agent {agent_name!r}:[/red] {ex}")
                continue

        if not self.scheduled_agents:
            print(
                "[yellow]No agents with schedules found. Add a 'schedule' section to your agent YAML files.[/yellow]"
            )

    async def run_scheduled_agent(self, agent_name: str) -> None:
        """Run a scheduled agent.

        Parameters
        ----------
        agent_name
            The name of the agent to run
        """
        agent = self.scheduled_agents.get(agent_name)
        if not agent:
            print(f"[red]Scheduled agent {agent_name!r} not found[/red]")
            return

        print(f"\n[bold cyan]Running scheduled agent:[/bold cyan] {agent_name}")
        print(f"[dim]Triggered at: {datetime.now(tz=UTC).isoformat()}[/dim]")

        analysis_agent = AnalysisAgent()
        try:
            # Scheduled agents run with no input payload
            result = await analysis_agent.acall(payload="", agent=agent)
            print(f"\n[green]Agent {agent_name!r} completed successfully[/green]")
            print(f"Result:\n{result}")
        except Exception as ex:
            print(f"[red]Agent {agent_name!r} failed:[/red] {ex}")

    def setup_jobs(self) -> None:
        """Set up scheduled jobs for all agents with schedules."""
        for agent_name, agent in self.scheduled_agents.items():
            if not agent.schedule:
                continue

            try:
                trigger = CronTrigger.from_crontab(agent.schedule.cron, timezone=UTC)
                self.scheduler.add_job(
                    self.run_scheduled_agent,
                    trigger=trigger,
                    args=[agent_name],
                    id=agent_name,
                    name=f"Agent: {agent_name}",
                    replace_existing=True,
                )
                print(
                    f"[green]Scheduled job for agent {agent_name!r}:[/green] {agent.schedule.cron}"
                )
            except Exception as ex:
                print(f"[red]Failed to schedule agent {agent_name!r}:[/red] {ex}")

    def _signal_handler(self, signum: int, frame: object) -> None:
        """Handle shutdown signals.

        Parameters
        ----------
        signum
            The signal number
        frame
            The current stack frame
        """
        print(f"\n[yellow]Received signal {signum}, shutting down...[/yellow]")
        self.shutdown_event.set()

    async def start(self) -> None:
        """Start the scheduler and run indefinitely."""
        from unpage.config import manager

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        print("[bold]Starting Unpage Agent Scheduler[/bold]")
        print(f"Profile: {manager.get_active_profile()}")
        print()

        self.load_scheduled_agents()

        if not self.scheduled_agents:
            print("[red]No scheduled agents found. Exiting.[/red]")
            sys.exit(1)

        print()
        self.setup_jobs()

        print("\n[bold green]Scheduler started successfully[/bold green]")
        print("Press Ctrl+C to stop\n")

        self.scheduler.start()

        try:
            # Wait for shutdown signal
            await self.shutdown_event.wait()
        finally:
            print("[yellow]Shutting down scheduler...[/yellow]")
            self.scheduler.shutdown(wait=True)
            print("[green]Scheduler stopped[/green]")
