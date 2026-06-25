"""Calendar MCP server — Phase 2 (Google Calendar API backend).

Exposes tools:
    list_events(date: str) -> dict
        Returns calendar events for the given date (YYYY-MM-DD).
    create_event(title: str, start_time: str, end_time: str) -> dict
        Creates an event with start/end in YYYY-MM-DD HH:MM.
    update_event(event_id: str, title: str = None, start_time: str = None, end_time: str = None) -> dict
        Updates specified fields on an event.
    delete_event(event_id: str) -> dict
        Deletes an event.

Transport: stdio (standard local-process MCP transport).
Run as a subprocess:
    uv run python -m app.mcp_servers.calendar_server
"""

import datetime
from mcp.server.fastmcp import FastMCP

from app.mcp_servers.calendar_auth import (
    fetch_events_for_date,
    get_calendar_client,
    parse_google_time,
)

mcp = FastMCP("calendar")


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
        events = fetch_events_for_date(date)
        return {"status": "success", "events": events}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def create_event(title: str, start_time: str, end_time: str) -> dict:
    """Creates a new calendar event on Google Calendar.

    Args:
        title: The summary/title of the event.
        start_time: Start time in 'YYYY-MM-DD HH:MM' format.
        end_time: End time in 'YYYY-MM-DD HH:MM' format.

    Returns:
        A dict with key 'status' ('success' | 'error') and the created event
        object details or error message.
    """
    try:
        local_tz = datetime.datetime.now().astimezone().tzinfo
        dt_start = datetime.datetime.strptime(start_time, "%Y-%m-%d %H:%M").replace(tzinfo=local_tz)
        dt_end = datetime.datetime.strptime(end_time, "%Y-%m-%d %H:%M").replace(tzinfo=local_tz)
        
        body = {
            "summary": title,
            "start": {"dateTime": dt_start.isoformat()},
            "end": {"dateTime": dt_end.isoformat()},
        }
        
        service = get_calendar_client()
        created_event = service.events().insert(calendarId="primary", body=body).execute()
        
        return {
            "status": "success",
            "event": {
                "id": created_event.get("id"),
                "title": created_event.get("summary", "(No title)"),
                "start_time": parse_google_time(created_event.get("start")),
                "end_time": parse_google_time(created_event.get("end")),
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def update_event(
    event_id: str,
    title: str = None,
    start_time: str = None,
    end_time: str = None,
) -> dict:
    """Updates one or more fields on an existing Google Calendar event.

    Args:
        event_id: The ID of the event to update.
        title: Optional new title.
        start_time: Optional new start time in 'YYYY-MM-DD HH:MM' format.
        end_time: Optional new end time in 'YYYY-MM-DD HH:MM' format.

    Returns:
        A dict with key 'status' ('success' | 'error') and the updated event
        object details or error message.
    """
    try:
        local_tz = datetime.datetime.now().astimezone().tzinfo
        body = {}
        if title is not None:
            body["summary"] = title
        if start_time is not None:
            dt_start = datetime.datetime.strptime(start_time, "%Y-%m-%d %H:%M").replace(tzinfo=local_tz)
            body["start"] = {"dateTime": dt_start.isoformat()}
        if end_time is not None:
            dt_end = datetime.datetime.strptime(end_time, "%Y-%m-%d %H:%M").replace(tzinfo=local_tz)
            body["end"] = {"dateTime": dt_end.isoformat()}

        if not body:
            return {"status": "error", "message": "No update fields specified."}

        service = get_calendar_client()
        updated_event = service.events().patch(
            calendarId="primary",
            eventId=event_id,
            body=body,
        ).execute()

        return {
            "status": "success",
            "event": {
                "id": updated_event.get("id"),
                "title": updated_event.get("summary", "(No title)"),
                "start_time": parse_google_time(updated_event.get("start")),
                "end_time": parse_google_time(updated_event.get("end")),
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def delete_event(event_id: str) -> dict:
    """Deletes an event from Google Calendar by its event ID.

    Args:
        event_id: The ID of the event to delete.

    Returns:
        A dict with key 'status' ('success' | 'error') and a success confirmation
        or error message.
    """
    try:
        service = get_calendar_client()
        service.events().delete(calendarId="primary", eventId=event_id).execute()
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    mcp.run(transport="stdio")
