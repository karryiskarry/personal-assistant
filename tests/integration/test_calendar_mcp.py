"""Integration test for the Calendar MCP roundtrip.

Verifies:
- The calendar_server subprocess spawns cleanly.
- The `list_events` tool is registered and discoverable via McpToolset.get_tools().
- Calling the tool returns the mocked events returned by the mock client
  when PERSONAL_ASSISTANT_CALENDAR_MOCK="true" is set in the environment.

This test does not hit the real Google Calendar API or load token.json, making it
deterministic and safe to run in a CI environment.
"""

import json
import os
import pytest
from mcp import StdioServerParameters

from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams

# Fixed test date and event so assertions are deterministic.
TEST_DATE = "2099-01-15"
TEST_EVENT_TITLE = "MCP Integration Test Event"
TEST_START_TIME = f"{TEST_DATE} 10:00:00"
TEST_END_TIME = f"{TEST_DATE} 11:00:00"

# Absolute path to the project root (parent of the app/ package).
_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)


def _build_toolset() -> McpToolset:
    """Return an McpToolset wired to a calendar_server subprocess using mock environment."""
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="uv",
                args=[
                    "run",
                    "--project",
                    _PROJECT_ROOT,
                    "python",
                    "-m",
                    "app.mcp_servers.calendar_server",
                ],
                cwd=_PROJECT_ROOT,
                # Pass the mock calendar flag to the subprocess via env var.
                env={
                    "PERSONAL_ASSISTANT_CALENDAR_MOCK": "true"
                },
            ),
            timeout=15.0,
        ),
        tool_filter=["list_events"],
    )


@pytest.mark.asyncio
async def test_calendar_mcp_tool_registration():
    """list_events is discoverable in the McpToolset after subprocess spawn."""
    toolset = _build_toolset()
    try:
        tools = await toolset.get_tools()
        tool_names = [t.name for t in tools]
        assert "list_events" in tool_names, (
            f"Expected 'list_events' in MCP tool list, got: {tool_names}"
        )
    finally:
        await toolset.close()


@pytest.mark.asyncio
async def test_calendar_mcp_tool_returns_mocked_event():
    """Calling list_events via the MCP session returns the mocked event exactly."""
    toolset = _build_toolset()
    try:
        # Call the tool directly at the MCP protocol level — no LLM involved.
        result = await toolset._execute_with_session(
            lambda session: session.call_tool(
                "list_events", arguments={"date": TEST_DATE}
            ),
            "Failed to call list_events via MCP session",
        )

        assert not result.isError, f"MCP tool call returned an error: {result}"
        assert result.content, "MCP tool call returned empty content"

        # FastMCP serialises dict return values as JSON text.
        payload = json.loads(result.content[0].text)

        assert payload["status"] == "success", (
            f"Expected status='success', got: {payload}"
        )
        events = payload["events"]
        assert len(events) == 1, (
            f"Expected exactly 1 event for {TEST_DATE}, got {len(events)}: {events}"
        )

        event = events[0]
        assert event["title"] == TEST_EVENT_TITLE
        assert event["start_time"] == TEST_START_TIME
        assert event["end_time"] == TEST_END_TIME
    finally:
        await toolset.close()
