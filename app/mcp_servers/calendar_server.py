"""Calendar MCP server — Phase 1 (mock SQLite backend).

Exposes one tool:
    list_events(date: str) -> dict
        Returns calendar events for the given date (YYYY-MM-DD) from the
        local SQLite `calendar_events` table via a read-only connection.

Transport: stdio (standard local-process MCP transport).
Run as a subprocess:
    uv run python -m app.mcp_servers.calendar_server
"""

from mcp.server.fastmcp import FastMCP

from app.db import get_readonly_db_connection

mcp = FastMCP("calendar")


@mcp.tool()
def list_events(date: str) -> dict:
    """Gets calendar events for a specific date.

    Args:
        date: The date in YYYY-MM-DD format.

    Returns:
        A dict with keys 'status' ('success' | 'error') and either
        'events' (list of dicts with id, title, start_time, end_time)
        or 'message' on error.
    """
    try:
        conn = get_readonly_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, title, start_time, end_time "
            "FROM calendar_events WHERE start_time LIKE ?",
            (f"{date}%",),
        )
        rows = cursor.fetchall()
        conn.close()
        return {"status": "success", "events": [dict(row) for row in rows]}
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    mcp.run(transport="stdio")
