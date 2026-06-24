"""Calendar MCP server — Phase 2 (Google Calendar API backend).

Exposes one tool:
    list_events(date: str) -> dict
        Returns calendar events for the given date (YYYY-MM-DD) from the
        Google Calendar API, mapped to the standard representation.

Transport: stdio (standard local-process MCP transport).
Run as a subprocess:
    uv run python -m app.mcp_servers.calendar_server
"""

import datetime
from mcp.server.fastmcp import FastMCP

from app.mcp_servers.calendar_auth import get_calendar_client

mcp = FastMCP("calendar")

def parse_google_time(dt_dict: dict) -> str:
    if not dt_dict:
        return ""
    if "dateTime" in dt_dict:
        dt_str = dt_dict["dateTime"]
        try:
            # datetime.fromisoformat handles timezone offsets and Z in Python 3.11+
            dt = datetime.datetime.fromisoformat(dt_str)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            # Fallback parsing
            part = dt_str.replace("T", " ")
            if "+" in part:
                part = part.split("+")[0]
            elif "-" in part.split(" ")[1]:
                time_part = part.split(" ")[1]
                part = part.split(" ")[0] + " " + time_part.split("-")[0]
            if "Z" in part:
                part = part.replace("Z", "")
            return part
    elif "date" in dt_dict:
        return f"{dt_dict['date']} 00:00:00"
    return ""

@mcp.tool()
def list_events(date: str) -> dict:
    """Gets calendar events for a specific date from Google Calendar.

    Args:
        date: The date in YYYY-MM-DD format.

    Returns:
        A dict with keys 'status' ('success' | 'error') and either
        'events' (list of dicts with id, title, start_time, end_time)
        or 'message' on error.
    """
    try:
        service = get_calendar_client()
        
        # Resolve time bounds using system's timezone offset
        local_tz = datetime.datetime.now().astimezone().tzinfo
        dt_min = datetime.datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=local_tz)
        dt_max = dt_min.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        time_min = dt_min.isoformat()
        time_max = dt_max.isoformat()
        
        events_result = service.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime"
        ).execute()
        
        items = events_result.get("items", [])
        
        events = []
        for item in items:
            events.append({
                "id": item.get("id"),
                "title": item.get("summary", "(No title)"),
                "start_time": parse_google_time(item.get("start")),
                "end_time": parse_google_time(item.get("end"))
            })
            
        return {"status": "success", "events": events}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    mcp.run(transport="stdio")
