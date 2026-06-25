import datetime
import os
import sys
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOKEN_PATH = os.path.join(PROJECT_ROOT, "token.json")

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
            return {
                "items": [
                    {
                        "id": "mock_event_1",
                        "summary": "MCP Integration Test Event",
                        "start": {"dateTime": "2099-01-15T10:00:00Z"},
                        "end": {"dateTime": "2099-01-15T11:00:00Z"}
                    }
                ]
            }
        elif op in ("insert", "patch"):
            body = self._kwargs.get("body", {})
            return {
                "id": self._kwargs.get("eventId", "mock_created_event_id"),
                "summary": body.get("summary", "Mock Event"),
                "start": body.get("start", {"dateTime": "2099-01-15T10:00:00Z"}),
                "end": body.get("end", {"dateTime": "2099-01-15T11:00:00Z"}),
            }
        elif op == "delete":
            return {}
        return {}

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
