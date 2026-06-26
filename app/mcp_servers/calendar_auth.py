import datetime
import json
import os
import sys
import uuid
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOKEN_PATH = os.path.join(PROJECT_ROOT, "token.json")

# Persists mock-mode create/update/delete calls to disk so they're visible to
# later list() calls — including across the process boundary between the MCP
# server subprocess (chat) and the main FastAPI process (Dashboard/Calendar
# tab), which don't share memory. Delete this file to reset mock state
# between demo recording takes.
MOCK_STATE_PATH = os.environ.get(
    "PERSONAL_ASSISTANT_MOCK_CALENDAR_STATE_PATH",
    os.path.join(PROJECT_ROOT, "mock_calendar_state.json"),
)


def _load_mock_events() -> list[dict]:
    if not os.path.exists(MOCK_STATE_PATH):
        return []
    try:
        with open(MOCK_STATE_PATH, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_mock_events(events: list[dict]) -> None:
    with open(MOCK_STATE_PATH, "w") as f:
        json.dump(events, f)


_DEFAULT_MOCK_START = {"dateTime": "2099-01-15T10:00:00Z"}
_DEFAULT_MOCK_END = {"dateTime": "2099-01-15T11:00:00Z"}


class MockEventsResource:
    def list(self, **kwargs):
        self._operation = "list"
        self._kwargs = kwargs
        return self

    def insert(self, **kwargs):
        self._operation = "insert"
        self._kwargs = kwargs
        return self

    def patch(self, **kwargs):
        self._operation = "patch"
        self._kwargs = kwargs
        return self

    def update(self, **kwargs):
        self._operation = "patch"
        self._kwargs = kwargs
        return self

    def delete(self, **kwargs):
        self._operation = "delete"
        self._kwargs = kwargs
        return self

    def execute(self):
        op = getattr(self, "_operation", "list")
        if op == "list":
            return {"items": self._list_items(self._kwargs.get("timeMin"), self._kwargs.get("timeMax"))}
        elif op == "insert":
            return self._insert_event(self._kwargs.get("body", {}))
        elif op == "patch":
            return self._patch_event(self._kwargs.get("eventId"), self._kwargs.get("body", {}))
        elif op == "delete":
            return self._delete_event(self._kwargs.get("eventId"))
        return {}

    @staticmethod
    def _insert_event(body: dict) -> dict:
        events = _load_mock_events()
        new_event = {
            "id": f"mock_created_{uuid.uuid4().hex[:8]}",
            "summary": body.get("summary", "Mock Event"),
            "start": body.get("start", _DEFAULT_MOCK_START),
            "end": body.get("end", _DEFAULT_MOCK_END),
        }
        events.append(new_event)
        _save_mock_events(events)
        return new_event

    @staticmethod
    def _patch_event(event_id: str, body: dict) -> dict:
        events = _load_mock_events()
        for event in events:
            if event["id"] == event_id:
                if "summary" in body:
                    event["summary"] = body["summary"]
                if "start" in body:
                    event["start"] = body["start"]
                if "end" in body:
                    event["end"] = body["end"]
                _save_mock_events(events)
                return event

        # Unknown ID — e.g. one of the synthetic demo events from
        # _list_items, or a made-up ID in a test — echo back the patch
        # without persisting, so updating an event that was never actually
        # created via insert() still succeeds rather than failing.
        return {
            "id": event_id or "mock_created_event_id",
            "summary": body.get("summary", "Mock Event"),
            "start": body.get("start", _DEFAULT_MOCK_START),
            "end": body.get("end", _DEFAULT_MOCK_END),
        }

    @staticmethod
    def _delete_event(event_id: str) -> dict:
        events = _load_mock_events()
        remaining = [e for e in events if e["id"] != event_id]
        if len(remaining) != len(events):
            _save_mock_events(remaining)
        return {}

    @staticmethod
    def _list_items(time_min, time_max):
        """Returns mock events for a list() call's [time_min, time_max] window.

        The integration tests query the fixed year 2099 specifically to stay
        deterministic, so that exact event is preserved when the window falls
        there. Any other window (e.g. "today" during a live demo recording)
        gets a believable, relative-to-now demo schedule instead, since the
        Dashboard/Calendar tab would otherwise just show that 2099 event
        regardless of what day was actually requested.
        """
        try:
            window_start = datetime.datetime.fromisoformat(time_min) if time_min else None
        except ValueError:
            window_start = None

        if window_start and window_start.year == 2099:
            return [
                {
                    "id": "mock_event_1",
                    "summary": "MCP Integration Test Event",
                    "start": _DEFAULT_MOCK_START,
                    "end": _DEFAULT_MOCK_END,
                }
            ]

        try:
            window_end = datetime.datetime.fromisoformat(time_max) if time_max else None
        except ValueError:
            window_end = None

        now = datetime.datetime.now().astimezone()

        def at(day_offset, hour, minute=0):
            return (now + datetime.timedelta(days=day_offset)).replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )

        demo_events = [
            ("Q1 Planning Session", at(-6, 10, 0), at(-6, 11, 0)),
            ("Onboarding Sync", at(-5, 14, 0), at(-5, 14, 30)),
            ("Design Review", at(-4, 11, 0), at(-4, 12, 0)),
            ("1:1 with Manager", at(-3, 9, 30), at(-3, 10, 0)),
            ("Client Call: Q2 Review", at(-2, 11, 0), at(-2, 11, 30)),
            ("Code Review Session", at(-1, 15, 0), at(-1, 16, 0)),
            ("Lunch with Team", at(-1, 12, 0), at(-1, 13, 0)),
            ("Morning Standup", at(0, 9, 0), at(0, 9, 15)),
            ("Deep Work: Capstone Demo Prep", at(0, 13, 0), at(0, 15, 0)),
            ("Gym Session", at(0, 17, 30), at(0, 18, 30)),
            ("Dentist Appointment", at(1, 10, 0), at(1, 11, 0)),
            ("Team Retro", at(2, 14, 0), at(2, 14, 30)),
            ("Birthday Dinner", at(4, 19, 0), at(4, 21, 0)),
        ]

        items = []
        for i, (title, start, end) in enumerate(demo_events):
            if window_start and window_end and not (window_start <= start <= window_end):
                continue
            items.append(
                {
                    "id": f"mock_demo_event_{i}",
                    "summary": title,
                    "start": {"dateTime": start.isoformat()},
                    "end": {"dateTime": end.isoformat()},
                }
            )

        # Merge in any events actually created/updated via insert()/patch()
        # in this or an earlier session, so they show up here too — not just
        # in the chat reply that confirmed creating them.
        for event in _load_mock_events():
            try:
                event_start = datetime.datetime.fromisoformat(event["start"]["dateTime"])
            except (KeyError, ValueError):
                continue
            if window_start and window_end and not (window_start <= event_start <= window_end):
                continue
            items.append(event)
        return items

class MockGoogleCalendarClient:
    def events(self):
        return MockEventsResource()

def get_calendar_client():
    if os.environ.get("PERSONAL_ASSISTANT_CALENDAR_MOCK") == "true":
        sys.stderr.write("WARNING: PERSONAL_ASSISTANT_CALENDAR_MOCK is active. Using MockGoogleCalendarClient.\n")
        sys.stderr.flush()
        return MockGoogleCalendarClient()

    if not os.path.exists(TOKEN_PATH):
        raise FileNotFoundError(
            f"Token file not found at {TOKEN_PATH}.\n"
            "Please run 'uv run python scripts/authorize_calendar.py' in the terminal first to authorize Google Calendar."
        )

    creds = Credentials.from_authorized_user_file(TOKEN_PATH, scopes=["https://www.googleapis.com/auth/calendar.events"])
    
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_PATH, "w") as token_file:
            token_file.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


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


def fetch_events_for_date(date: str) -> list[dict]:
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
            "end_time": parse_google_time(item.get("end")),
            "all_day": "date" in (item.get("start") or {})
        })
    return events


def fetch_events_for_range(start_date: str, end_date: str) -> list[dict]:
    service = get_calendar_client()
    
    # Resolve time bounds using system's timezone offset
    local_tz = datetime.datetime.now().astimezone().tzinfo
    dt_min = datetime.datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=local_tz)
    dt_max = datetime.datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=local_tz).replace(
        hour=23, minute=59, second=59, microsecond=999999
    )
    
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
            "end_time": parse_google_time(item.get("end")),
            "all_day": "date" in (item.get("start") or {})
        })
    return events
