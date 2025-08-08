from pathlib import Path
import pytest
from fastmcp import Client


@pytest.mark.asyncio
async def test_docs_have_all_tools(mcp_client: Client) -> None:
    tools = await mcp_client.list_tools()
    server_tool_names = [tool.name for tool in tools]
    docs_dir = Path(__file__).parent.parent / "docs"
    all_docs_content = ""
    for filename in docs_dir.glob("**/*.mdx"):
        all_docs_content += filename.read_text(encoding='utf-8')
    for server_tool_name in server_tool_names:
        assert server_tool_name in all_docs_content, (
            f"Tool '{server_tool_name}' not found in documentation"
        )
