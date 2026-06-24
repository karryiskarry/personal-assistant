import calendar
import datetime
import json
import re

from .db import get_db_connection, get_readonly_db_connection


def get_current_date() -> dict:
    """Gets the current local date in YYYY-MM-DD format."""
    return {"date": datetime.date.today().strftime("%Y-%m-%d")}


def create_task(
    title: str,
    description: str = "",
    due_date: str = "",
    recurrence: str = "",
    tag: str = "",
    source: str = "manual",
) -> dict:
    """Creates a new task in the user's task tracker.

    Args:
        title: The title of the task.
        description: A description of the task (use empty string if none).
        due_date: The due date in YYYY-MM-DD format (defaults to the current day if not specified).
        recurrence: The recurrence rule: 'daily', 'weekly', 'biweekly', 'monthly', or None (use empty string if none).
        tag: A categorization tag (e.g. 'chore', 'work', 'health', use empty string if none).
        source: The source of task creation ('manual', 'nl_capture', or 'plan_generated').
    """
    try:
        # Normalize recurrence value to None if empty or 'none'
        rec_val = recurrence.lower().strip() if recurrence else None
        if rec_val in ["none", ""]:
            rec_val = None

        # Normalize and default due date to current day if empty/None
        due_date_val = due_date.strip() if due_date else ""
        if not due_date_val:
            due_date_val = datetime.date.today().strftime("%Y-%m-%d")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO tasks (title, description, due_date, recurrence, status, tag, source) VALUES (?, ?, ?, ?, 'open', ?, ?)",
            (
                title,
                description if description else None,
                due_date_val,
                rec_val,
                tag if tag else None,
                source if source else "manual",
            ),
        )
        task_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return {
            "status": "success",
            "message": f"Task '{title}' created successfully with ID {task_id}.",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def update_task(
    task_id: int,
    title: str | None = None,
    description: str | None = None,
    due_date: str | None = None,
    recurrence: str | None = None,
    tag: str | None = None,
) -> dict:
    """Updates properties of an existing task in the user's task tracker.

    Args:
        task_id: The ID of the task to update.
        title: The new title of the task (omit or leave empty to keep unchanged).
        description: The new description of the task (omit or leave empty to keep unchanged).
        due_date: The new due date in YYYY-MM-DD format (omit or leave empty to keep unchanged).
        recurrence: The new recurrence rule: 'daily', 'weekly', 'biweekly', 'monthly', or None (omit or leave empty to keep unchanged).
        tag: The new categorization tag (e.g. 'chore', 'work', 'health', omit or leave empty to keep unchanged).
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if task exists
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        task = cursor.fetchone()
        if not task:
            conn.close()
            return {"status": "error", "message": f"No task found with ID {task_id}."}

        updates = []
        params = []

        if title is not None and title != "":
            updates.append("title = ?")
            params.append(title)
        if description is not None:
            updates.append("description = ?")
            params.append(description if description != "" else None)
        if due_date is not None:
            updates.append("due_date = ?")
            params.append(due_date if due_date != "" else None)
        if recurrence is not None:
            rec_val = recurrence.lower().strip() if recurrence else None
            if rec_val in ["none", ""]:
                rec_val = None
            updates.append("recurrence = ?")
            params.append(rec_val)
        if tag is not None:
            updates.append("tag = ?")
            params.append(tag if tag != "" else None)

        if not updates:
            conn.close()
            return {"status": "success", "message": "No updates specified."}

        params.append(task_id)
        query = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, tuple(params))
        conn.commit()
        conn.close()

        return {"status": "success", "message": f"Task {task_id} updated successfully."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def advance_recurring_task(cursor, task_row) -> None:
    """Calculates the next due date for a recurring task and inserts a new open task row."""
    recurrence = task_row["recurrence"]
    if not recurrence or recurrence.lower() == "none":
        return

    due_date_str = task_row["due_date"]
    if not due_date_str:
        due_date_str = datetime.date.today().strftime("%Y-%m-%d")

    try:
        base_date = datetime.datetime.strptime(due_date_str, "%Y-%m-%d").date()
    except Exception:
        base_date = datetime.date.today()

    rec = recurrence.lower()
    if rec == "daily":
        next_due = base_date + datetime.timedelta(days=1)
    elif rec == "weekly":
        next_due = base_date + datetime.timedelta(days=7)
    elif rec == "biweekly":
        next_due = base_date + datetime.timedelta(days=14)
    elif rec == "monthly":
        month = base_date.month
        year = base_date.year
        day = base_date.day
        if month == 12:
            month = 1
            year += 1
        else:
            month += 1
        last_day = calendar.monthrange(year, month)[1]
        next_due = datetime.date(year, month, min(day, last_day))
    else:
        return

    next_due_str = next_due.strftime("%Y-%m-%d")

    # Insert next instance with parent_task_id set to task_row['id']
    cursor.execute(
        "INSERT INTO tasks (title, description, due_date, recurrence, status, tag, source, parent_task_id) "
        "VALUES (?, ?, ?, ?, 'open', ?, ?, ?)",
        (
            task_row["title"],
            task_row["description"],
            next_due_str,
            task_row["recurrence"],
            task_row["tag"],
            task_row["source"],
            task_row["id"],
        ),
    )


def complete_task(task_id: int) -> dict:
    """Marks a task as completed in the task tracker.

    Args:
        task_id: The ID of the task to complete.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch current task status and recurrence
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        task_row = cursor.fetchone()

        if not task_row:
            conn.close()
            return {"status": "error", "message": f"No task found with ID {task_id}."}

        # Update status to completed and set completed_at timestamp
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "UPDATE tasks SET status = 'completed', completed_at = ? WHERE id = ?",
            (now_str, task_id),
        )
        rows_affected = cursor.rowcount

        # If it was not completed before, advance recurrence
        if (
            task_row["status"] != "completed"
            and task_row["recurrence"]
            and task_row["recurrence"].lower()
            in ["daily", "weekly", "biweekly", "monthly"]
        ):
            advance_recurring_task(cursor, task_row)

        conn.commit()
        conn.close()

        if rows_affected > 0:
            return {
                "status": "success",
                "message": f"Task {task_id} marked as completed.",
            }

        return {"status": "error", "message": f"No task found with ID {task_id}."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_period_start(date: datetime.date, frequency: str, anchor: datetime.date | None = None) -> datetime.date:
    frequency = frequency.lower().strip()
    if frequency == "daily":
        return date
    elif frequency == "weekly":
        return date - datetime.timedelta(days=date.weekday())
    elif frequency == "biweekly":
        if anchor is None:
            raise ValueError("Anchor is required for biweekly frequency")
        idx = (date - anchor).days // 14
        return anchor + datetime.timedelta(days=idx * 14)
    elif frequency == "monthly":
        return date.replace(day=1)
    else:
        raise ValueError(f"Unknown frequency: {frequency}")


def get_previous_period_start(period_start: datetime.date, frequency: str) -> datetime.date:
    frequency = frequency.lower().strip()
    if frequency == "daily":
        return period_start - datetime.timedelta(days=1)
    elif frequency == "weekly":
        return period_start - datetime.timedelta(days=7)
    elif frequency == "biweekly":
        return period_start - datetime.timedelta(days=14)
    elif frequency == "monthly":
        return (period_start - datetime.timedelta(days=1)).replace(day=1)
    else:
        raise ValueError(f"Unknown frequency: {frequency}")


def get_month_start_relative(base_month_start: datetime.date, offset: int) -> datetime.date:
    year = base_month_start.year
    month = base_month_start.month
    total_months = year * 12 + (month - 1) + offset
    new_year = total_months // 12
    new_month = (total_months % 12) + 1
    return datetime.date(new_year, new_month, 1)


def create_habit(name: str, frequency: str, description: str | None = None) -> dict:
    """Creates a new habit to track going forward.

    Use this when the user wants to START tracking a new recurring behaviour
    (e.g. 'I want to track flossing daily', 'add a habit for meditation').
    Do NOT use this to record that the user already did something today — use
    log_habit for that.

    Args:
        name: The name of the habit (e.g. 'Flossing', 'Morning run').
        frequency: How often the habit recurs: 'daily' (e.g. "every day"),
            'weekly' (e.g. "every week"), 'biweekly' (e.g. "every 2 weeks"),
            or 'monthly' (e.g. "once a month").
        description: An optional description of the habit (None if not provided).
    """
    freq = frequency.lower().strip() if frequency else ""
    if freq not in ("daily", "weekly", "biweekly", "monthly"):
        return {
            "status": "error",
            "message": f"Invalid frequency '{frequency}'. Must be 'daily', 'weekly', 'biweekly', or 'monthly'.",
        }

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO habits (name, description, frequency) VALUES (?, ?, ?)",
            (name, description if description else None, freq),
        )
        habit_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return {
            "status": "success",
            "message": f"Created new {freq} habit '{name}' (ID {habit_id}).",
            "habit_id": habit_id,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def log_habit(habit_id: int, date: str) -> dict:
    """Logs completion of a habit for a specific date.

    Args:
        habit_id: The ID of the habit to log.
        date: The date in YYYY-MM-DD format.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO habit_logs (habit_id, date, status) VALUES (?, ?, 'completed')",
            (habit_id, date),
        )
        conn.commit()
        conn.close()
        return {
            "status": "success",
            "message": f"Logged habit {habit_id} for date {date}.",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def log_workout(exercise: str, sets: str, date: str, notes: str) -> dict:
    """Logs a workout session with a list of sets and optional notes.

    Args:
        exercise: The name of the exercise (e.g. 'Bench Press').
        sets: A JSON string representing a list of sets, e.g. '[{"reps": 5, "weight_kg": 80.0}, {"reps": 3, "weight_kg": 85.0}]'.
        date: The date in YYYY-MM-DD format.
        notes: Optional notes about the workout session (use empty string if none).
    """
    try:
        # Validate sets is valid JSON
        try:
            parsed_sets = json.loads(sets)
            if not isinstance(parsed_sets, list):
                return {"status": "error", "message": "sets must be a JSON array."}
        except Exception:
            return {"status": "error", "message": "sets is not a valid JSON string."}

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO workout_logs (exercise, sets, date, notes) VALUES (?, ?, ?, ?)",
            (
                exercise,
                sets,
                date,
                notes if notes else None,
            ),
        )
        log_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return {
            "status": "success",
            "message": f"Logged workout session: {exercise} with {len(parsed_sets)} sets for {date} (ID {log_id}).",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def delete_item(table_name: str, item_id: int) -> dict:
    """Deletes an item from the user's data (tasks, habits, or workout logs).

    Args:
        table_name: The table to delete from: 'tasks', 'habits', or 'workout_logs'.
        item_id: The ID of the item to delete.
    """
    if table_name not in ["tasks", "habits", "workout_logs"]:
        return {
            "status": "error",
            "message": f"Unauthorized deletion from table: {table_name}",
        }

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {table_name} WHERE id = ?", (item_id,))
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()
        if rows_affected > 0:
            return {
                "status": "success",
                "message": f"Successfully deleted item {item_id} from {table_name}.",
            }
        return {
            "status": "error",
            "message": f"No item found with ID {item_id} in {table_name}.",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def execute_db_query(sql_query: str) -> dict:
    """Executes a read-only SELECT SQL query on the database for analysis and trends.

    Args:
        sql_query: A SELECT SQL query.
    """
    cleaned = sql_query.strip().lower()
    if not cleaned.startswith("select"):
        return {"status": "error", "message": "Only SELECT queries are allowed."}

    # Prevent common DML/DDL commands
    if re.search(
        r"(?i)\b(update|delete|insert|drop|alter|create|truncate|replace|merge|vacuum)\b",
        sql_query,
    ):
        return {"status": "error", "message": "Disallowed DML/DDL operations detected."}

    try:
        conn = get_readonly_db_connection()
        cursor = conn.cursor()
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        conn.close()

        results = [dict(row) for row in rows]
        return {"status": "success", "results": results}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_calendar_events(date: str) -> dict:
    """Gets calendar events for a specific date (YYYY-MM-DD).

    Args:
        date: The date in YYYY-MM-DD format.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, title, start_time, end_time FROM calendar_events WHERE start_time LIKE ? ORDER BY start_time ASC",
            (f"{date}%",),
        )
        rows = cursor.fetchall()
        conn.close()
        return {"status": "success", "events": [dict(row) for row in rows]}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_habit_streaks() -> dict:
    """Calculates the current streak and last logged date for all active habits."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, frequency, created_at FROM habits "
            "ORDER BY CASE frequency WHEN 'daily' THEN 0 WHEN 'weekly' THEN 1 WHEN 'biweekly' THEN 2 WHEN 'monthly' THEN 3 ELSE 4 END, name ASC"
        )
        habits = cursor.fetchall()

        streaks = {}
        today = datetime.date.today()
        cutoff_date = (today - datetime.timedelta(days=83)).strftime("%Y-%m-%d")

        for h in habits:
            habit_id = h["id"]
            name = h["name"]

            created_at_str = h["created_at"] or ""
            if " " in created_at_str:
                created_at_str = created_at_str.split(" ")[0]
            try:
                created_date = datetime.datetime.strptime(created_at_str, "%Y-%m-%d").date()
            except Exception:
                created_date = datetime.date.min

            freq = h["frequency"].lower().strip()

            cursor.execute(
                "SELECT date FROM habit_logs WHERE habit_id = ? ORDER BY date DESC",
                (habit_id,),
            )
            logs = [
                datetime.datetime.strptime(row["date"], "%Y-%m-%d").date()
                for row in cursor.fetchall()
            ]

            streak = 0
            if logs:
                log_periods = set()
                for log_date in logs:
                    log_periods.add(get_period_start(log_date, freq, created_date))

                current_period = get_period_start(today, freq, created_date)

                if current_period in log_periods:
                    current_check = current_period
                else:
                    prev_period = get_previous_period_start(current_period, freq)
                    if prev_period in log_periods:
                        current_check = prev_period
                    else:
                        current_check = current_period

                while current_check in log_periods:
                    streak += 1
                    current_check = get_previous_period_start(current_check, freq)

            # Query completed dates for heatmap (last 84 days, or last ~365 days for monthly)
            if freq == "monthly":
                habit_cutoff_date = (today - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
            else:
                habit_cutoff_date = cutoff_date

            cursor.execute(
                "SELECT date FROM habit_logs WHERE habit_id = ? AND date >= ? ORDER BY date DESC",
                (habit_id, habit_cutoff_date),
            )
            recent_logs = [row["date"] for row in cursor.fetchall()]

            streak_units = {
                "daily": "day",
                "weekly": "week",
                "biweekly": "biweekly",
                "monthly": "month",
            }

            streaks[name] = {
                "habit_id": habit_id,
                "frequency": h["frequency"],
                "current_streak": streak,
                "streak_unit": streak_units.get(freq, "day"),
                "last_logged": logs[0].strftime("%Y-%m-%d") if logs else None,
                "created_at": h["created_at"],
                "completed_dates": recent_logs,
            }
        conn.close()
        return {"status": "success", "streaks": streaks}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# Exposed as a plain tool; confirmation is handled conversationally by the agent
# (the agent instruction requires warning the user before calling this tool).
# require_confirmation=True is not used because the ADK confirmation event is not
# handled by the single-shot HTMX /chat endpoint and produces a silent empty response.
delete_item_tool = delete_item


def calculate_warmup_sets(target_weight: float) -> dict:
    """Calculates a deterministic warm-up progression based on target weight.

    The number of sets, percentages, and reps are calculated using a fixed formula
    and lookup tables. All weights are rounded to the nearest 2.5kg increment.

    Args:
        target_weight: The target working weight in kg.
    """
    try:
        # Determine number of sets
        if target_weight <= 40.0:
            num_sets = 2
        elif target_weight <= 100.0:
            num_sets = 3
        elif target_weight <= 160.0:
            num_sets = 4
        else:
            num_sets = 5

        # Lookup table for [percentage, reps] per set count
        lookup = {
            2: [(0.50, 8), (0.75, 4)],
            3: [(0.40, 8), (0.60, 5), (0.80, 3)],
            4: [(0.40, 8), (0.55, 5), (0.70, 4), (0.85, 2)],
            5: [(0.40, 8), (0.55, 5), (0.70, 4), (0.80, 2), (0.90, 1)],
        }

        sets_config = lookup[num_sets]
        warmup_sets = []
        for idx, (pct, reps) in enumerate(sets_config):
            raw_weight = target_weight * pct
            # Round to the nearest 2.5kg standard plate increment
            rounded_weight = round(raw_weight / 2.5) * 2.5
            pct_str = f"{int(pct * 100)}%"

            warmup_sets.append(
                {
                    "set_number": idx + 1,
                    "percentage": pct_str,
                    "weight_kg": rounded_weight,
                    "reps": reps,
                }
            )

        return {
            "status": "success",
            "target_weight_kg": target_weight,
            "warmup_sets": warmup_sets,
            "recommendation": "Perform warm-up sets with 1-2 minutes rest between sets before starting your working sets.",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def set_exercise_active(exercise_name: str, active: bool) -> dict:
    """Sets the active status of an exercise in the training plan.

    Args:
        exercise_name: The name of the exercise (e.g. 'Bench Press').
        active: True to mark it active, False to deactivate.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if the exercise already exists in plan_exercises
        cursor.execute(
            "SELECT id FROM plan_exercises WHERE exercise_name = ?", (exercise_name,)
        )
        row = cursor.fetchone()

        active_val = 1 if active else 0

        if row:
            cursor.execute(
                "UPDATE plan_exercises SET active = ? WHERE exercise_name = ?",
                (active_val, exercise_name),
            )
            message = f"Exercise '{exercise_name}' updated to active={active_val}."
        else:
            cursor.execute(
                "INSERT INTO plan_exercises (exercise_name, active) VALUES (?, ?)",
                (exercise_name, active_val),
            )
            message = f"Exercise '{exercise_name}' inserted as active={active_val}."

        conn.commit()
        conn.close()
        return {"status": "success", "message": message}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def sync_active_exercises(active_exercise_names: list[str]) -> dict:
    """Synchronizes the list of active training plan exercises.

    Sets active=1 for every name in active_exercise_names (inserting if new)
    and active=0 for any currently active plan exercises not present in the list.

    Args:
        active_exercise_names: A list of exercise names that are active in the new plan.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Normalize names and remove duplicates
        normalized_names = list(
            {name.strip() for name in active_exercise_names if name and name.strip()}
        )

        if not normalized_names:
            conn.close()
            return {
                "status": "error",
                "message": "sync_active_exercises cannot be called with an empty list. If you wish to deactivate a single exercise, call set_exercise_active instead.",
            }

        # Deactivate all active exercises not present in the new plan
        placeholders = ",".join(["?"] * len(normalized_names))
        cursor.execute(
            f"UPDATE plan_exercises SET active = 0 WHERE active = 1 AND exercise_name NOT IN ({placeholders})",
            tuple(normalized_names),
        )

        # Activate each specified exercise (updating active status, inserting if not present)
        for name in normalized_names:
            cursor.execute(
                "SELECT id FROM plan_exercises WHERE exercise_name = ?", (name,)
            )
            row = cursor.fetchone()
            if row:
                cursor.execute(
                    "UPDATE plan_exercises SET active = 1 WHERE exercise_name = ?",
                    (name,),
                )
            else:
                cursor.execute(
                    "INSERT INTO plan_exercises (exercise_name, active) VALUES (?, 1)",
                    (name,),
                )

        conn.commit()
        conn.close()
        return {
            "status": "success",
            "message": f"Synchronized active exercises. Active count: {len(normalized_names)}.",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def resolve_weekday_date(weekday_name: str) -> dict:
    """Resolves a weekday name to its nearest date (YYYY-MM-DD) on or after today.

    Args:
        weekday_name: The name of the weekday (e.g. 'Monday', 'Saturday').
    """
    weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    name_clean = weekday_name.strip().lower()
    if name_clean not in weekdays:
        raise ValueError(f"Invalid weekday name '{weekday_name}'. Must be one of Monday-Sunday.")

    target_idx = weekdays.index(name_clean)
    today = datetime.date.today()
    today_idx = today.weekday()

    days_ahead = target_idx - today_idx
    if days_ahead < 0:
        days_ahead += 7

    target_date = today + datetime.timedelta(days=days_ahead)
    return {
        "date": target_date.strftime("%Y-%m-%d"),
        "weekday": name_clean.capitalize()
    }

