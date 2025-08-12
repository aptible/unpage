from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import dspy
from fastmcp import Client, FastMCP
from pydantic import BaseModel, Field
from pydantic_yaml import parse_yaml_file_as

from unpage.config import manager
from unpage.knowledge.graph import Graph
from unpage.mcp import Context, build_mcp_server
from unpage.plugins.base import PluginManager
from unpage.utils import wildcard_or_regex_match_any


class Agent(BaseModel):
    name: str = Field(description="The name of the agent", default="")
    description: str = Field(description="A description of the agent and when it should be used")
    prompt: str = Field(description="The prompt to use for the agent")
    tools: list[str] = Field(description="The tools the agent has access to")


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
    def __init__(self, profile: str) -> None:
        super().__init__()

        self.profile = profile
        self.config_dir = manager.get_profile_directory(profile)
        self.config = manager.get_profile_config(profile)
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

    async def get_mcp_server(self) -> FastMCP:
        if self.mcp_server is None:
            self.mcp_server = await build_mcp_server(
                Context(
                    profile=self.profile,
                    config=self.config,
                    plugins=PluginManager(config=self.config),
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

        async with self.unpage_agent(signature, agent.tools, max_iters=max_iters) as unpage:
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
        allowed_tool_patterns: list[str] | None = None,
        max_iters: int = 5,
    ) -> AsyncGenerator[dspy.Module, None]:
        """Yield a configured Unpage agent."""
        allowed_tool_patterns = allowed_tool_patterns or ["*"]

        async with Client(await self.get_mcp_server()) as client:
            yield dspy.ReAct(
                signature,
                tools=[
                    dspy.Tool.from_mcp_tool(client.session, tool)
                    for tool in await client.list_tools()
                    if wildcard_or_regex_match_any(allowed_tool_patterns, tool.name)
                ],
                max_iters=max_iters,
            )
