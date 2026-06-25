#!/usr/bin/env python3
import os
from google_auth_oauthlib.flow import InstalledAppFlow

# Resolve paths relative to the script's location (project root is parent of scripts/)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
CREDENTIALS_PATH = os.path.join(PROJECT_ROOT, "credentials.json")
TOKEN_PATH = os.path.join(PROJECT_ROOT, "token.json")

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

def main():
    if not os.path.exists(CREDENTIALS_PATH):
        print(f"Error: {CREDENTIALS_PATH} not found. Please ensure credentials.json is placed in the project root.")
        return

    print("Starting interactive Google Calendar authorization flow...")
    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, scopes=SCOPES)
    # Run a local server on a random port (port=0) to handle the redirect
    creds = flow.run_local_server(port=0)

    # Save credentials to token.json
    with open(TOKEN_PATH, "w") as token_file:
        token_file.write(creds.to_json())

    print(f"Successfully authorized and saved token to {TOKEN_PATH}")

if __name__ == "__main__":
    main()
