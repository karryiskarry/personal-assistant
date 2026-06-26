# Personal Assistant v1

A personal AI agent that tracks tasks, habits, and workouts through natural language — built with Google's Agent Development Kit (ADK 2.0) and a custom FastAPI dashboard.

## Problem

Managing daily tasks, recurring habits, and workout progress usually means juggling several disconnected apps. This project explores whether a single agent — one that can capture quick natural-language input, decompose vague goals into structured plans, and answer grounded questions about your own data — can replace that fragmentation with one coherent assistant.

## Solution

An ADK 2.0 agent backed by SQLite, exposed through a FastAPI/HTMX dashboard. Every request to the agent is classified into one of three paths:

- **Capture** — direct, unambiguous input ("log my squats 3x5 at 80kg") parsed straight into a database row, created immediately.
- **Plan generation** — vague goal-style requests ("structure my push/pull/legs week") trigger a completeness check that asks clarifying questions if needed, then drafts and creates the resulting tasks directly.
- **Advisory/analysis** — read-only questions ("how's my squat progress looking") answered strictly from the user's own logged data, never fabricated.

Two domain-specific Agent Skills (`household-planning`, `workout-planning`) are loaded only when the request is relevant to that domain, keeping the core agent instructions lean.

## Architecture

- **Database layer** (`app/db.py`) — SQLite, six tables: tasks, habits, habit_logs, workout_logs, calendar_events, plan_exercises.
- **Agent layer** (`app/agent.py`, `app/tools.py`) — Gemini-powered ADK agent with structured tools for every mutation (create/complete/delete, with explicit deletion confirmation), a read-only SQL query tool for advisory questions, dynamic skill loading via a `before_agent_callback`, and a `McpToolset` connection to a local Calendar MCP server for real Google Calendar access.
- **Calendar MCP server** (`app/mcp_servers/calendar_server.py`, `app/mcp_servers/calendar_auth.py`) — a `FastMCP` server run as a separate process over stdio, exposing `list_events`, `create_event`, `update_event`, and `delete_event` tools backed by the real Google Calendar API via OAuth2 with the `calendar.events` write scope (`scripts/authorize_calendar.py` runs the one-time consent flow). Falls back to a mocked response set when `PERSONAL_ASSISTANT_CALENDAR_MOCK=true`, used in tests.
- **Web layer** (`app/main.py`, `app/templates/`) — FastAPI + Jinja2 + HTMX, five navigable tabs (Dashboard, Tasks, Habits, Workouts, Calendar) with a persistent chat sidebar, served as a single `uvicorn` process — no Node/npm toolchain.

Design decisions worth calling out:
- Deterministic logic (thresholds, date math, warm-up set calculations, recurrence advancement) lives in code, never in model reasoning — the model is only used for genuine judgment calls.
- Recurring tasks preserve history via `parent_task_id` lineage rather than mutating a single row in place.
- The Dashboard tab aggregates "what's due today" via plain SQL — no LLM call on every tab visit.
- The Dashboard and Calendar tab's visual widgets call the real Google Calendar API directly (no LLM involvement — `fetch_events_for_date`/`fetch_events_for_range` in `app/mcp_servers/calendar_auth.py`, shared with the MCP server's `list_events` tool), with no caching — an earlier short-TTL cache was removed after it caused stale data to display following a chat-driven calendar edit, since the MCP server runs as a separate process with no way to invalidate it. They fall back to the seeded mock dataset only if OAuth isn't set up (`token.json` missing) or the API call fails — keeping that deterministic aggregation path independent of the agent/MCP path, with a real-data-first, mock-as-fallback design.
- Calendar event creation/modification/deletion via chat follows the same explicit-confirmation discipline as deletion elsewhere in the app — and, unlike tasks/habits, even *creating* a calendar event requires confirmation first, since it writes to the user's real external calendar, not just local data.
- Tests run against an isolated temporary SQLite database (`tests/conftest.py` patches `DB_PATH` per test) — never the live file, after a real incident where routine test runs silently wiped real active-exercise data. The same isolation problem applies across process boundaries for MCP subprocess tests, solved via the `PERSONAL_ASSISTANT_DB_PATH`/`PERSONAL_ASSISTANT_CALENDAR_MOCK`/`PERSONAL_ASSISTANT_MOCK_CALENDAR_STATE_PATH` environment variables rather than `monkeypatch`, which doesn't cross processes.
- A spawned MCP subprocess does **not** inherit its parent process's full environment by default — the MCP SDK only forwards a fixed safe list (`HOME`, `PATH`, etc.) unless `env=` is passed explicitly to `StdioServerParameters`. `agent.py`'s `McpToolset` forwards `PERSONAL_ASSISTANT_CALENDAR_MOCK` explicitly for this reason; omitting it silently sends chat-routed calendar calls to the real Google Calendar API even with mock mode set on the parent process.
- The agent resolves names/descriptions to internal database IDs itself before any mutation or confirmation — it never asks the user to supply or look up a raw ID. The same explicit-confirmation pattern applies to any plan-altering tool call (e.g. `sync_active_exercises`) based on assumed defaults, not just deletions.

## Features

- Natural-language task, habit, and workout logging
- Goal-style plan generation (e.g. chore breakdowns, weekly training splits) with clarifying questions for vague requests
- Deterministic warm-up set calculator (no LLM math)
- "Current Lifts" progress tracking for exercises in the active training plan
- Per-habit completion heatmap across all four habit frequencies (daily/weekly/biweekly/monthly), each with a frequency-appropriate grid shape and time window
- Workout history grouped into per-date session cards, rather than a flat exercise-by-exercise list
- Recurring task support with safe undo (no duplicate/orphaned instances)
- Real Google Calendar integration via a custom MCP server with OAuth2 authentication — read, create, update, and delete events through natural-language chat, with explicit confirmation before any write
- Explicit deletion confirmation on all destructive actions, extended to any plan-altering tool call based on assumed defaults
- Medical disclaimers on fitness advice; all advisory answers grounded in actual logged data

## Requirements

Before you begin, ensure you have:
- **uv**: Python package manager, used for all dependency management — [Install](https://docs.astral.sh/uv/getting-started/installation/)
- **agents-cli**: Install with `uv tool install google-agents-cli`
- **Google Cloud SDK**: for GCP services — [Install](https://cloud.google.com/sdk/docs/install)

## Setup

Install `agents-cli` and its skills if not already installed:

```bash
uvx google-agents-cli setup
```

Install project dependencies:

```bash
agents-cli install
```

Run the dashboard:

```bash
uv run uvicorn app.main:app --reload --port 8000
```

Open `http://127.0.0.1:8000`.

You can also test the bare ADK agent without the dashboard via `agents-cli playground` (auto-reloads on save).

## Project Structure

```
personal-assistant/
├── app/
│   ├── agent.py          # Main agent logic, skill loading
│   ├── tools.py          # Structured tools (CRUD, warm-up calculator, query)
│   ├── db.py             # SQLite schema and migrations
│   ├── main.py           # FastAPI routes and dashboard sections
│   ├── templates/        # Jinja2 + HTMX templates
│   └── skills/           # household-planning/, workout-planning/ SKILL.md files
├── tests/                # Unit, integration, and eval tests
├── GEMINI.md             # AI-assisted development guide
└── pyproject.toml        # Project dependencies
```

## Development Commands

| Command | Description |
| --- | --- |
| `agents-cli install` | Install dependencies using uv |
| `agents-cli playground` | Launch local development environment for the bare agent |
| `agents-cli lint` | Run code quality checks |
| `agents-cli eval` | Evaluate agent behavior |
| `uv run pytest tests/unit tests/integration` | Run unit and integration tests |
| `agents-cli deploy` | Deploy agent to Agent Runtime |
| `agents-cli publish gemini-enterprise` | Register deployed agent to Gemini Enterprise |

## Known Limitations / Planned Enhancements

- Exercise-name matching for plan/progress tracking is exact-string only (no fuzzy matching)
- No proactive/ambient nudges — the agent is reactive to the dashboard or chat, not scheduled
