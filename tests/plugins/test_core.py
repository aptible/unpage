from typing import TYPE_CHECKING, cast
from fastmcp import Client
import pytest
from freezegun.api import FrozenDateTimeFactory

if TYPE_CHECKING:
    from mcp.types import TextContent


@pytest.mark.asyncio
async def test_core_calculate(mcp_client: Client) -> None:
    result = await mcp_client.call_tool("core_calculate", {"expression": "1 + 1"})
    result = cast("TextContent", result.content[0])
    assert float(result.text) == 2.0


@pytest.mark.asyncio
async def test_core_current_datetime(mcp_client: Client, freezer: FrozenDateTimeFactory) -> None:
    current_datetime = "2025-01-01T12:00:00Z"
    freezer.move_to(current_datetime)
    result = await mcp_client.call_tool("core_current_datetime")
    result = cast("TextContent", result.content[0])
    assert result.text.strip('"') == current_datetime
