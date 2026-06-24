import os
import sys
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOKEN_PATH = os.path.join(PROJECT_ROOT, "token.json")

class MockEventsResource:
    def list(self, **kwargs):
        self._kwargs = kwargs
        return self

    def execute(self):
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

    creds = Credentials.from_authorized_user_file(TOKEN_PATH, scopes=["https://www.googleapis.com/auth/calendar.readonly"])
    
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_PATH, "w") as token_file:
            token_file.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)
