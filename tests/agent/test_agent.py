from pydantic_yaml import parse_yaml_raw_as
import pytest
from fastmcp import Client

from unpage.agent.analysis import Agent
from unpage.agent.utils import get_agent_template, load_agent


@pytest.mark.asyncio
async def test_default_template_has_all_tools(mcp_client: Client) -> None:
    tools = await mcp_client.list_tools()
    server_tool_names = [tool.name for tool in tools]
    default_template = get_agent_template("default")
    default_template_tools = parse_yaml_raw_as(Agent, default_template).tools
    assert sorted(default_template_tools) == sorted(server_tool_names)
