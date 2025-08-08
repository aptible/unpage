from pathlib import Path
import pytest
from fastmcp import Client


@pytest.mark.asyncio
async def test_docs_have_all_tools(mcp_client: Client) -> None:
    tools = await mcp_client.list_tools()
    tool_info = {}
    for tool in tools:
        plugin, tool_name = tool.name.split("_", maxsplit=1)
        if plugin not in tool_info:
            tool_info[plugin] = []
        tool_info[plugin].append(tool_name)
    docs_dir = Path(__file__).parent.parent.parent / "docs" / "plugins"
    for filename in docs_dir.glob("**/*.mdx"):
        for plugin in tool_info:
            if filename.name == f"{plugin}.mdx":
                doc_content = filename.read_text(encoding="utf-8")
                for tool_name in tool_info[plugin]:
                    assert tool_name in doc_content, (
                        f"Tool '{tool_name}' not found in documentation for plugin '{plugin}' in {filename}"
                    )
                tool_info.pop(plugin)
                break
    assert not tool_info, f"Tools not documented: {', '.join(tool_info.keys())}"
