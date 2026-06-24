"""Integration test for the Calendar MCP roundtrip.

Verifies:
- The calendar_server subprocess spawns cleanly.
- The `list_events` tool is registered and discoverable via McpToolset.get_tools().
- Calling the tool returns the exact event seeded in an isolated temp DB —
  not hardcoded production data.

Isolation strategy: the subprocess reads DB_PATH from the
PERSONAL_ASSISTANT_DB_PATH environment variable (added in app/db.py). We pass
the temp file path through StdioServerParameters.env so the subprocess never
touches the live personal_assistant.db — the same safety guarantee as
conftest.py's monkeypatch, but across the process boundary.

No LLM / Gemini API calls are made — this test only exercises the MCP
subprocess spawn → stdio transport → tool list → tool call chain.
"""

import json
import os
import sqlite3
import tempfile

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


def _seed_temp_db(db_path: str) -> None:
    """Create schema and insert one known calendar event into the temp DB."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # Minimal schema — only the table the calendar server queries.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS calendar_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    cursor.execute(
        "INSERT INTO calendar_events (title, start_time, end_time) VALUES (?, ?, ?)",
        (TEST_EVENT_TITLE, TEST_START_TIME, TEST_END_TIME),
    )
    conn.commit()
    conn.close()


def _build_toolset(db_path: str) -> McpToolset:
    """Return an McpToolset wired to a calendar_server subprocess using db_path."""
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
                # Pass the isolated DB path to the subprocess via env var.
                env={"PERSONAL_ASSISTANT_DB_PATH": db_path},
            ),
            timeout=15.0,
        ),
        tool_filter=["list_events"],
    )


@pytest.mark.asyncio
async def test_calendar_mcp_tool_registration():
    """list_events is discoverable in the McpToolset after subprocess spawn."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        _seed_temp_db(db_path)
        toolset = _build_toolset(db_path)
        try:
            tools = await toolset.get_tools()
            tool_names = [t.name for t in tools]
            assert "list_events" in tool_names, (
                f"Expected 'list_events' in MCP tool list, got: {tool_names}"
            )
        finally:
            await toolset.close()
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


@pytest.mark.asyncio
async def test_calendar_mcp_tool_returns_seeded_event():
    """Calling list_events via the MCP session returns the seeded event exactly."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        _seed_temp_db(db_path)
        toolset = _build_toolset(db_path)
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
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
