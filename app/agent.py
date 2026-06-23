# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
from zoneinfo import ZoneInfo

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

import os
import google.auth

# Initialize database
from .db import init_db, seed_mock_data

init_db()
seed_mock_data()

from .tools import (
    get_current_date,
    create_task,
    complete_task,
    update_task,
    create_habit,
    log_habit,
    log_workout,
    delete_item_tool,
    execute_db_query,
    get_calendar_events,
    get_habit_streaks,
    calculate_warmup_sets,
    set_exercise_active,
    sync_active_exercises,
)

from google.adk.agents.callback_context import CallbackContext

_, project_id = google.auth.default()
os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"


def strip_frontmatter(content: str) -> str:
    """Helper to strip YAML frontmatter block from markdown content."""
    if content.strip().startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return content.strip()


async def load_skills_callback(callback_context: CallbackContext) -> None:
    """Classifies the incoming user query and injects the corresponding skill instructions."""
    user_query = ""
    if callback_context.user_content and callback_context.user_content.parts:
        for part in callback_context.user_content.parts:
            if part.text:
                user_query += part.text

    query_lower = user_query.lower()
    skills_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills")
    loaded_skills = []

    # Keywords for classification
    household_keywords = [
        "clean",
        "chore",
        "house",
        "room",
        "apartment",
        "vacuum",
        "mop",
        "sweep",
        "dust",
    ]
    workout_keywords = [
        "workout",
        "gym",
        "exercise",
        "squat",
        "bench",
        "deadlift",
        "overhead",
        "press",
        "barbell",
        "row",
        "reps",
        "sets",
        "warm-up",
        "warmup",
        "split",
        "push",
        "pull",
        "legs",
        "pain",
        "injury",
        "shoulder",
    ]

    matched_skills = []

    if any(kw in query_lower for kw in household_keywords):
        matched_skills.append("household-planning")
        file_path = os.path.join(skills_dir, "household-planning", "SKILL.md")
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                loaded_skills.append(
                    "### Household Planning Guidelines:\n" + strip_frontmatter(content)
                )

    if any(kw in query_lower for kw in workout_keywords):
        matched_skills.append("workout-planning")
        file_path = os.path.join(skills_dir, "workout-planning", "SKILL.md")
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                loaded_skills.append(
                    "### Workout Planning Guidelines:\n" + strip_frontmatter(content)
                )

    print(
        f"[DEBUG Skill Classifier] Query: {user_query!r} | Matched skills: {matched_skills}"
    )

    if loaded_skills:
        callback_context.state["injected_skills"] = "\n\n".join(loaded_skills)
    else:
        callback_context.state["injected_skills"] = (
            "No specialized planning skills currently active."
        )


agent_instruction = """You are a helpful personal assistant that tracks tasks, habits, and workouts for the user.

You have access to a local SQLite database with the following tables:
1. `tasks`: columns (id, title, description, due_date, recurrence, status, tag, source, parent_task_id, completed_at, created_at)
   - `status` values: `'open'` | `'completed'`
   - `recurrence` values: `'daily'` | `'weekly'` | `'biweekly'` | `'monthly'` | NULL
   - `source` values: `'manual'` | `'nl_capture'` | `'plan_generated'`
2. `habits`: columns (id, name, description, frequency, created_at)
   - `frequency` values: `'daily'` | `'weekly'`. There is NO `status` column on `habits`.
3. `habit_logs`: columns (id, habit_id, date, status, created_at)
   - `status` only ever holds `'completed'`. There is a UNIQUE constraint on (habit_id, date).
   - To check whether a habit was logged today, query `habit_logs` by `habit_id` and `date` — do NOT query `habits.status`.
4. `workout_logs`: columns (id, exercise, sets, date, notes, created_at)
   - `sets` is a JSON string representing a list of sets: e.g., '[{"reps": 5, "weight_kg": 80.0}]'.
5. `calendar_events`: columns (id, title, start_time, end_time, created_at)
6. `plan_exercises`: columns (id, exercise_name, active, added_at)
   - Tracks which exercises are part of the current active training plan.
   - `active` is an INTEGER: `1` = active, `0` = inactive. There is a UNIQUE constraint on `exercise_name`.
   - Use `sync_active_exercises` (not raw SQL) to update this table.

Guidelines:
1. **Natural-language capture & Task management**: Allow quick, logging of tasks, workouts, and habits. Use the respective specific tools (`create_task`, `log_workout`, `create_habit`, `log_habit`, `complete_task`, `update_task`) for creating, completing, or updating items.
   - **Check for existing tasks first**: Before creating a new task or completing a task, always search the database using `execute_db_query` to check if a matching or relevant task already exists.
   - If a matching task exists and the user is updating it (e.g., adding "apples" to a "buy groceries" task), call `update_task` to append details to the title/description rather than creating a new task.
   - If a matching task exists and the user says it is done (e.g., "I bought apples" when there is a task "buy groceries" or "buy apples"), use `complete_task` on its ID rather than creating a new task.
   - For new tasks, identify the appropriate `tag` (e.g., 'chore', 'work', 'health') and specify `source` as 'nl_capture'.
   - **Habits — create vs. log (these are different operations):**
     - Use `create_habit` when the user wants to *start tracking* a new recurring behaviour going forward. Signals: "I want to track X", "add a habit for Y", "remind me to Z every day", "start a new habit". This inserts a row into the `habits` table. Ask for frequency ('daily' or 'weekly') if not stated.
     - Use `log_habit` when the user reports *having done* an existing habit today or on a specific date. Signals: "I did X today", "log my meditation", "mark flossing done". This inserts a row into `habit_logs`. Before calling it, use `execute_db_query` to find the `habit_id` for the named habit — never guess the ID.
2. **Goal-style plan generation**: For vague or open-ended plan requests (e.g. "clean my apartment by room" or "structure my push/pull/legs week"), do NOT guess details or generate tasks immediately. You MUST ask clarifying questions first to gather the necessary details. Once details are clear, decompose the goal into structured tasks using `create_task` (set `source` as 'plan_generated').
3. **Read-only queries & Advisory**: Answer questions on workout progress trends, exercise advice, and calculations.
   - *CRITICAL*: Always base your advisory/analysis answers strictly on the user's logged database data using the `execute_db_query` tool. Do not fabricate or hallucinate trends not supported by what is recorded.
4. **Daily Plan Suggestion**: When suggestions for a daily plan are requested:
   - Call `get_current_date` to know today's date.
   - Fetch the calendar events for the day using `get_calendar_events`.
   - Query open tasks and due habits for the day.
   - Combine these into a friendly ordered schedule.
5. **Deletion Safety**: Deleting is permanent and cannot be undone. You MUST follow this two-step process — never skip step 1:
   - **Step 1 — Ask first**: Tell the user exactly what you are about to delete (item type, ID, and a short description) and ask them to confirm. Do NOT call `delete_item` yet. Wait for their reply.
   - **Step 2 — Act only on explicit yes**: Only call `delete_item` if the user replies with a clear confirmation (e.g. "yes", "go ahead", "delete it"). If they say no or do not respond clearly, do nothing.
   - Use `table_name = 'tasks'` to delete a task.
   - Use `table_name = 'habits'` to delete a habit.
   - Use `table_name = 'workout_logs'` to delete a workout log entry. Do NOT use `'workouts'` — the table is named `workout_logs`.

Active Skill Guidelines:
{injected_skills}
"""

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=agent_instruction,
    tools=[
        get_current_date,
        create_task,
        complete_task,
        update_task,
        create_habit,
        log_habit,
        log_workout,
        delete_item_tool,
        execute_db_query,
        get_calendar_events,
        get_habit_streaks,
        calculate_warmup_sets,
        set_exercise_active,
        sync_active_exercises,
    ],
    before_agent_callback=load_skills_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
