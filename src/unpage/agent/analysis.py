from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import dspy
from fastmcp import Client, FastMCP
from pydantic import BaseModel, Field
from pydantic_yaml import parse_yaml_file_as

from unpage.config import EnvironmentVariablesMixin, PluginConfig, manager
from unpage.knowledge.graph import Graph
from unpage.mcp import Context, build_mcp_server
from unpage.plugins.base import REGISTRY, PluginManager
from unpage.utils import wildcard_or_regex_match_any


class PartialConfigForAgent(EnvironmentVariablesMixin, BaseModel):
    plugins: dict[str, PluginConfig] = Field(default_factory=dict)


class AgentTestPayload(BaseModel):
    description: str | None = Field(
        description="A description of the test payload and what it is testing",
        default=None,
    )
    payload: str = Field(description="The test payload to use")


class AgentSchedule(BaseModel):
    cron: str = Field(
        description=(
            "Cron expression for scheduling the agent. Supports:\n"
            "- Standard 5-field: minute hour day month day_of_week (e.g., '0 10 2 * *')\n"
            "- Extended 6-field: second minute hour day month day_of_week (e.g., '*/2 * * * * *' for every 2 seconds)\n"
            "- Aliases: @hourly, @daily, @weekly, @monthly, @yearly, @annually"
        )
    )


class Agent(BaseModel):
    name: str = Field(description="The name of the agent", default="")
    description: str = Field(description="A description of the agent and when it should be used")
    prompt: str = Field(description="The prompt to use for the agent")
    tools: list[str] = Field(description="The tools the agent has access to")
    config: PartialConfigForAgent = Field(
        description="Agent specific configuration to add to, or even override, the global config",
        default_factory=PartialConfigForAgent,
    )
    test_payloads: dict[str, AgentTestPayload] | None = Field(
        description="Test payloads for testing the agent",
        default=None,
    )
    schedule: AgentSchedule | None = Field(
        description="Optional schedule configuration for periodic agent runs",
        default=None,
    )

    def required_plugins_from_tools(self) -> list[str]:
        allowed_tool_patterns = (
            ["*"]
            if not self.tools
            else list({f"{p.split('_', maxsplit=1)[0]}*" for p in self.tools})
        )
        return [
            plugin_name
            for plugin_name in REGISTRY
            if wildcard_or_regex_match_any(allowed_tool_patterns, f"{plugin_name}_")
        ]


class SelectAgent(dspy.Signature):
    """You are an expert Site Reliability Engineer with deep expertise in alert triage.

    You will be given an alert payload from an alerting system and a list of
    agent descriptions. Your task is to select the most relevant agent to use to
    analyze the given alert. You may use the tools you're given to get more
    information about the alert and the incident, if necessary.

    Note that you MUST select an agent from the list of available agents. If you
    don't know which agent to use, select the "default" agent.
    """

    payload: str = dspy.InputField(
        description="The payload received from the alerting system",
    )

    available_agents: dict[str, Agent] = dspy.InputField(
        description="The list of agents to select from",
    )

    selected_agent_name: str = dspy.OutputField(
        description="The selected agent",
    )

    reasoning: str = dspy.OutputField(
        description="The reasoning behind choosing the selected agent",
    )


class Analyze(dspy.Signature):
    payload: str = dspy.InputField(description="The alert payload to triage")
    analysis: str = dspy.OutputField(description="The triage analysis of the alert payload")


class AnalysisAgent(dspy.Module):
    def __init__(self) -> None:
        super().__init__()

        self.profile = manager.get_active_profile()
        self.config_dir = manager.get_active_profile_directory()
        self.config = manager.get_active_profile_config()
        self.llm_settings = self.config.plugins["llm"].settings

        self.available_agents: dict[str, Agent] = {}
        for agent_file in self.config_dir.glob("agents/**/*.yaml"):
            try:
                agent = parse_yaml_file_as(Agent, agent_file)
            except Exception as ex:
                print(f"Failed to load agent {agent_file}: {ex}")
                continue
            agent.name = agent_file.stem
            self.available_agents[agent.name] = agent

        self.mcp_server = None

    async def get_mcp_server(self, agent: Agent | None) -> FastMCP:
        if self.mcp_server is None:
            config = (
                self.config
                if agent is None or agent.config is None
                else self.config.merge_plugins(agent.config.plugins)
            )
            self.mcp_server = await build_mcp_server(
                Context(
                    profile=self.profile,
                    config=config,
                    plugins=PluginManager(config=config),
                    graph=Graph(self.config_dir / "graph.json"),
                )
            )
        return self.mcp_server

    async def acall(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        params = {
            "model": self.llm_settings["model"],
            "api_key": self.llm_settings["api_key"],
            **(
                {"temperature": self.llm_settings["temperature"]}
                if not self.llm_settings["model"].startswith("bedrock/")
                else {}
            ),
            "max_tokens": self.llm_settings["max_tokens"],
            "cache": self.llm_settings["cache"],
        }
        with dspy.context(
            lm=dspy.LM(**params),
        ):
            return await super().acall(*args, **kwargs)

    async def aforward(
        self,
        payload: str,
        agent: Agent | None = None,
        route_only: bool = False,
        max_iters: int = 5,
    ) -> str:
        """Triage the given alert payload using an appropriate prompt."""
        if agent is None:
            selected_agent, reasoning = await self.select_agent(payload)
        else:
            selected_agent, reasoning = agent, "(explicitly selected)"

        if route_only:
            return f"Routing to the {selected_agent.name!r} agent\n  - Agent description: {selected_agent.description}\n  - Selection reasoning: {reasoning}"

        return await self.analyze(
            payload=payload,
            agent=selected_agent,
            max_iters=max_iters,
        )

    async def analyze(
        self,
        payload: str,
        agent: Agent,
        max_iters: int = 5,
    ) -> str:
        """Triage the given alert payload using the selected agent."""
        # Inject the selected prompt into the signature.
        signature = Analyze.with_instructions(agent.prompt)

        async with self.unpage_agent(signature, agent, max_iters=max_iters) as unpage:
            result = await unpage.acall(payload=payload)
            return result.analysis

    async def select_agent(
        self,
        payload: str,
    ) -> tuple[Agent, str]:
        """Select the most relevant prompt to use to triage the given alert payload.

        Returns the selected agent and the reasoning behind the selection.
        """
        async with self.unpage_agent(SelectAgent) as prompt_selector:
            result = await prompt_selector.acall(
                payload=payload,  # type: ignore[reportCallIssue]
                # Pass only prompt names and descriptions to avoid confusing the LLM
                # with the prompt contents.
                available_agents={
                    n: {"name": n, "description": p.description}
                    for n, p in self.available_agents.items()
                },
            )
            return self.available_agents[result.selected_agent_name], result.reasoning

    @asynccontextmanager
    async def unpage_agent(
        self,
        signature: type[dspy.Signature],
        agent: Agent | None = None,
        max_iters: int = 5,
    ) -> AsyncGenerator[dspy.Module, None]:
        """Yield a configured Unpage agent."""
        allowed_tool_patterns = ["*"] if agent is None or not agent.tools else agent.tools

        async with Client(await self.get_mcp_server(agent)) as client:
            yield dspy.ReAct(
                signature,
                tools=[
                    dspy.Tool.from_mcp_tool(client.session, tool)
                    for tool in await client.list_tools()
                    if wildcard_or_regex_match_any(allowed_tool_patterns, tool.name)
                ],
                max_iters=max_iters,
            )
