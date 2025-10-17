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
        self.running_tasks: set[asyncio.Task] = set()
        self._event_loop: asyncio.AbstractEventLoop | None = None
        self._shutdown_count = 0
        self._force_shutdown = asyncio.Event()

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

    async def _run_agent_task(self, agent_name: str) -> None:
        """Internal task wrapper that tracks running tasks.

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
        except asyncio.CancelledError:
            print(f"[yellow]Agent {agent_name!r} was cancelled during shutdown[/yellow]")
            raise
        except Exception as ex:
            print(f"[red]Agent {agent_name!r} failed:[/red] {ex}")

    def run_scheduled_agent(self, agent_name: str) -> None:
        """Run a scheduled agent (called by APScheduler).

        This wraps the async task and tracks it for cancellation during shutdown.

        Parameters
        ----------
        agent_name
            The name of the agent to run
        """
        # Use the stored event loop
        if self._event_loop is None:
            print(f"[red]Error: Event loop not initialized for agent {agent_name!r}[/red]")
            return

        # Create async task in the main event loop
        task = self._event_loop.create_task(self._run_agent_task(agent_name))

        # Track the task
        self.running_tasks.add(task)

        # Remove from tracking when done
        task.add_done_callback(self.running_tasks.discard)

    def _parse_cron_expression(self, cron_expr: str) -> CronTrigger:
        """Parse a cron expression into a CronTrigger.

        Supports:
        - Standard 5-field cron: minute hour day month day_of_week
        - Extended 6-field cron: second minute hour day month day_of_week
        - Cron aliases: @hourly, @daily, @weekly, @monthly, @yearly, @annually

        Parameters
        ----------
        cron_expr
            The cron expression to parse

        Returns
        -------
        CronTrigger
            The configured CronTrigger instance

        Raises
        ------
        ValueError
            If the cron expression is invalid
        """
        cron_expr = cron_expr.strip()

        # Handle cron aliases
        cron_aliases = {
            "@hourly": "0 * * * *",
            "@daily": "0 0 * * *",
            "@weekly": "0 0 * * 0",
            "@monthly": "0 0 1 * *",
            "@yearly": "0 0 1 1 *",
            "@annually": "0 0 1 1 *",
        }

        if cron_expr.lower() in cron_aliases:
            cron_expr = cron_aliases[cron_expr.lower()]

        # Split the expression to count fields
        fields = cron_expr.split()

        if len(fields) == 5:
            # Standard 5-field cron: minute hour day month day_of_week
            return CronTrigger.from_crontab(cron_expr, timezone=UTC)
        elif len(fields) == 6:
            # Extended 6-field cron: second minute hour day month day_of_week
            second, minute, hour, day, month, day_of_week = fields
            return CronTrigger(
                second=second,
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week,
                timezone=UTC,
            )
        else:
            raise ValueError(
                f"Invalid cron expression: {cron_expr!r}. "
                f"Expected 5 or 6 fields, got {len(fields)}. "
                f"Supported formats: '* * * * *' (5 fields) or '* * * * * *' (6 fields with seconds)"
            )

    def setup_jobs(self) -> None:
        """Set up scheduled jobs for all agents with schedules."""
        for agent_name, agent in self.scheduled_agents.items():
            if not agent.schedule:
                continue

            try:
                trigger = self._parse_cron_expression(agent.schedule.cron)
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
        self._shutdown_count += 1

        if self._shutdown_count == 1:
            print(f"\n[yellow]Received signal {signum}, shutting down gracefully...[/yellow]")
            print("[yellow]Waiting up to 10 seconds for running agents to complete...[/yellow]")
            print("[dim]Press Ctrl+C again to force immediate shutdown[/dim]")
            self.shutdown_event.set()
        else:
            print(f"\n[red]Received signal {signum} again, forcing immediate shutdown![/red]")
            self._force_shutdown.set()
            # Force exit
            sys.exit(1)

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

        # Start the scheduler with the current event loop
        self.scheduler.start()

        # Store the event loop for job execution
        self._event_loop = asyncio.get_running_loop()

        try:
            # Wait for shutdown signal
            await self.shutdown_event.wait()
        finally:
            print("[yellow]Shutting down scheduler...[/yellow]")

            # Shutdown scheduler immediately (don't wait for jobs)
            self.scheduler.shutdown(wait=False)

            # Cancel all running agent tasks
            if self.running_tasks:
                task_count = len(self.running_tasks)
                print(f"[yellow]Cancelling {task_count} running agent task(s)...[/yellow]")

                for task in self.running_tasks:
                    task.cancel()

                # Wait for tasks with timeout and progress
                if self.running_tasks:
                    timeout = 10.0
                    start_time = asyncio.get_event_loop().time()

                    # Create a task to wait for all running tasks
                    gather_task = asyncio.gather(*self.running_tasks, return_exceptions=True)

                    # Progress bar loop
                    while not gather_task.done():
                        elapsed = asyncio.get_event_loop().time() - start_time
                        remaining = max(0, timeout - elapsed)

                        if remaining <= 0 or self._force_shutdown.is_set():
                            # Timeout or forced shutdown
                            if not self._force_shutdown.is_set():
                                print("\n[red]Timeout reached, forcing shutdown[/red]")
                            gather_task.cancel()
                            break

                        # Show progress bar
                        progress = elapsed / timeout
                        bar_width = 40
                        filled = int(bar_width * progress)
                        bar = "█" * filled + "░" * (bar_width - filled)
                        print(
                            f"\r[yellow]Waiting: [{bar}] {remaining:.1f}s remaining[/yellow]",
                            end="",
                            flush=True,
                        )

                        # Short sleep to not spam the console
                        try:
                            await asyncio.wait_for(asyncio.shield(gather_task), timeout=0.1)
                            break  # Tasks completed
                        except TimeoutError:
                            continue  # Keep waiting and updating progress

                    print()  # New line after progress bar

            print("[green]Scheduler stopped[/green]")
