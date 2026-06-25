import datetime
import json
import os

import markdown
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from google.adk.runners import InMemoryRunner
from google.genai import types

from .agent import root_agent
from .db import get_db_connection, get_readonly_db_connection
from .tools import (
    advance_recurring_task,
    get_calendar_events,
    get_calendar_events_range,
    get_habit_streaks,
    get_month_start_relative,
    get_period_start,
)

app = FastAPI(title="Personal Assistant Dashboard")

# Set up templates directory
templates_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
templates = Jinja2Templates(directory=templates_path)

# Initialize the ADK agent runner
runner = InMemoryRunner(agent=root_agent, app_name="app")


def format_display_date(date_val, long_format=False, with_weekday=False) -> str:
    """
    Formats a date object or YYYY-MM-DD string into display format.
    If long_format=True, returns e.g. "Wednesday, 24. June 2026".
    If with_weekday=True, returns e.g. "Wednesday, 24.06.2026".
    Otherwise, returns "DD.MM.YYYY" (e.g. "24.06.2026").
    """
    if not date_val:
        return ""

    # Try parsing string to date object
    if isinstance(date_val, str):
        # Could be YYYY-MM-DD or YYYY-MM-DD HH:MM:SS
        date_str = date_val.split(" ")[0]
        try:
            parts = date_str.split("-")
            if len(parts) == 3:
                year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                date_obj = datetime.date(year, month, day)
            else:
                return date_val  # Fallback if not parsable
        except Exception:
            return date_val
    else:
        date_obj = date_val

    weekdays = {
        0: "Monday",
        1: "Tuesday",
        2: "Wednesday",
        3: "Thursday",
        4: "Friday",
        5: "Saturday",
        6: "Sunday"
    }

    if long_format:
        months = {
            1: "January",
            2: "February",
            3: "March",
            4: "April",
            5: "May",
            6: "June",
            7: "July",
            8: "August",
            9: "September",
            10: "October",
            11: "November",
            12: "December"
        }
        weekday_name = weekdays.get(date_obj.weekday(), "")
        month_name = months.get(date_obj.month, "")
        return f"{weekday_name}, {date_obj.day}. {month_name} {date_obj.year}"
    elif with_weekday:
        weekday_name = weekdays.get(date_obj.weekday(), "")
        return f"{weekday_name}, {date_obj.day:02d}.{date_obj.month:02d}.{date_obj.year}"
    else:
        return f"{date_obj.day:02d}.{date_obj.month:02d}.{date_obj.year}"


def render_calendar_events_html(events, show_date=False, empty_message="No events scheduled.") -> str:
    html = ""
    if not events:
        return f"<div style='color: var(--text-muted); font-size: 14px; font-style: italic;'>{empty_message}</div>"
    
    import itertools
    
    if show_date:
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Determine the unique dates in order and find the first date >= today
        unique_dates = sorted(list({e["start_time"].split(" ")[0] for e in events if " " in e["start_time"]}))
        target_scroll_date = None
        for d in unique_dates:
            if d >= today_str:
                target_scroll_date = d
                break

        for date_part, group in itertools.groupby(events, key=lambda e: e["start_time"].split(" ")[0] if " " in e["start_time"] else e["start_time"]):
            formatted_date = format_display_date(date_part, with_weekday=True)
            items_html = ""
            
            # Identify group parameters
            id_attr = 'id="calendar-today-group"' if date_part == target_scroll_date else ""
            is_past_day = date_part < today_str
            group_class = "calendar-day-group past-day" if is_past_day else "calendar-day-group"
            
            for e in group:
                if e.get("all_day"):
                    time_str = '<span class="calendar-duration">All day</span>'
                else:
                    start_time = (
                        e["start_time"].split(" ")[1] if " " in e["start_time"] else e["start_time"]
                    )
                    end_time = (
                        e["end_time"].split(" ")[1] if " " in e["end_time"] else e["end_time"]
                    )
                    time_str = f'<span class="calendar-duration">{start_time[:5]} - {end_time[:5]}</span>'
                
                is_today = (date_part == today_str)
                is_past = (e.get("end_time") and e["end_time"] < now_str)
                class_name = "calendar-item past" if (is_today and is_past) else "calendar-item"
                
                items_html += f"""
                <div class="{class_name}">
                    <div class="calendar-title">{e["title"]}</div>
                    <div class="calendar-time">{time_str}</div>
                </div>
                """
            html += f"""
            <div class="{group_class}" {id_attr}>
                <div class="calendar-day-header">
                    <div class="calendar-day-date">{formatted_date}</div>
                </div>
                <div class="calendar-day-entries">
                    {items_html}
                </div>
            </div>
            """
        return html

    for e in events:
        if e.get("all_day"):
            time_str = '<span class="calendar-duration">All day</span>'
        else:
            start_time = (
                e["start_time"].split(" ")[1] if " " in e["start_time"] else e["start_time"]
            )
            end_time = (
                e["end_time"].split(" ")[1] if " " in e["end_time"] else e["end_time"]
            )
            time_str = f'<span class="calendar-duration">{start_time[:5]} - {end_time[:5]}</span>'

        html += f"""
        <div class="calendar-item">
            <div class="calendar-title">{e["title"]}</div>
            <div class="calendar-time">{time_str}</div>
        </div>
        """
    return html


def get_dashboard_section_html() -> str:
    return """
    <div class="dashboard-three-split">
        <!-- Today's Schedule -->
        <div class="section-card">
            <div class="section-title">
                <span>Today's Schedule</span>
            </div>
            <div class="calendar-list"
                 hx-get="/calendar/today"
                 hx-trigger="load, refresh-dashboard from:body"
                 hx-swap="innerHTML">
                <div style="color: var(--text-muted); font-size: 14px; font-style: italic;">Loading today's schedule...</div>
            </div>
        </div>

        <!-- Open & Overdue Tasks -->
        <div class="section-card">
            <div class="section-title">
                <span>Open & Overdue Tasks</span>
            </div>
            <div class="task-list"
                 hx-get="/dashboard/tasks"
                 hx-trigger="load, refresh-dashboard from:body"
                 hx-swap="innerHTML">
                <div style="color: var(--text-muted); font-size: 14px; font-style: italic;">Loading tasks...</div>
            </div>
        </div>

        <!-- Habits To Do Today -->
        <div class="section-card">
            <div class="section-title">
                <span>Habits To Do Today</span>
            </div>
            <div class="habit-grid"
                 hx-get="/dashboard/habits"
                 hx-trigger="load, refresh-dashboard from:body"
                 hx-swap="innerHTML">
                <div style="color: var(--text-muted); font-size: 14px; font-style: italic;">Loading habits...</div>
            </div>
        </div>
    </div>
    """


def get_tasks_section_html() -> str:
    return """
    <div class="section-card">
        <div class="section-title">
            Task Tracker
        </div>
        <div class="task-list"
             hx-get="/tasks/items"
             hx-trigger="load, refresh-dashboard from:body"
             hx-swap="innerHTML">
            <div style="color: var(--text-muted); font-size: 14px; font-style: italic;">Loading tasks...</div>
        </div>
    </div>
    """


def get_habits_section_html() -> str:
    return """
    <div class="section-card">
        <div class="section-title">
            Daily Habits
        </div>
        <div class="habit-grid"
             hx-get="/habits/items"
             hx-trigger="load, refresh-dashboard from:body"
             hx-swap="innerHTML">
            <div style="color: var(--text-muted); font-size: 14px; font-style: italic;">Loading habits...</div>
        </div>
    </div>
    """


def get_workouts_section_html() -> str:
    return """
    <div style="display: flex; flex-direction: column; gap: 24px;">
        <!-- Current Lifts Card -->
        <div class="section-card">
            <div class="section-title">
                Current Lifts
            </div>
            <div class="current-lifts-list"
                 hx-get="/workouts/lifts"
                 hx-trigger="load, refresh-dashboard from:body"
                 hx-swap="innerHTML">
                <div style="color: var(--text-muted); font-size: 14px; font-style: italic;">Loading current lifts...</div>
            </div>
        </div>

        <!-- Workout History Card -->
        <div class="section-card">
            <div class="section-title">
                Workout History
            </div>
            <div class="workout-list"
                 hx-get="/workouts/items"
                 hx-trigger="load, refresh-dashboard from:body"
                 hx-swap="innerHTML">
                <div style="color: var(--text-muted); font-size: 14px; font-style: italic;">Loading workouts...</div>
            </div>
        </div>
    </div>
    """


def get_calendar_section_html() -> str:
    return """
    <div class="section-card">
        <div class="section-title">
            Calendar Events
        </div>
        <div class="calendar-list"
             hx-get="/calendar/items"
             hx-trigger="load, refresh-dashboard from:body"
             hx-swap="innerHTML">
            <div style="color: var(--text-muted); font-size: 14px; font-style: italic;">Loading calendar events...</div>
        </div>
    </div>
    """


async def render_section(request: Request, tab: str, section_html: str):
    if request.headers.get("HX-Request") == "true":
        return HTMLResponse(content=section_html)

    today_date = format_display_date(datetime.date.today(), long_format=True)
    return templates.TemplateResponse(
        request,
        "index.html",
        {"today_date": today_date, "active_tab": tab, "content_html": section_html},
    )


@app.get("/", response_class=HTMLResponse)
async def read_dashboard_root(request: Request):
    return await render_section(request, "dashboard", get_dashboard_section_html())


@app.get("/dashboard", response_class=HTMLResponse)
async def read_dashboard_tab(request: Request):
    return await render_section(request, "dashboard", get_dashboard_section_html())


@app.get("/tasks", response_class=HTMLResponse)
async def get_tasks_section(request: Request):
    return await render_section(request, "tasks", get_tasks_section_html())


@app.get("/tasks/items", response_class=HTMLResponse)
async def get_tasks_items():
    try:
        conn = get_readonly_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM tasks ORDER BY status DESC, due_date ASC, id DESC"
        )
        tasks = cursor.fetchall()
        conn.close()
    except Exception as e:
        return HTMLResponse(
            content=f"<div style='color: var(--accent-red)'>Error: {e}</div>"
        )

    html = ""
    if not tasks:
        html = "<div style='color: var(--text-muted); font-size: 14px; font-style: italic;'>No tasks logged yet.</div>"

    today_str = datetime.date.today().strftime("%Y-%m-%d")
    for t in tasks:
        checked = "checked" if t["status"] == "completed" else ""
        tag_class = t["tag"] if t["tag"] else ""
        is_overdue = t["due_date"] is not None and t["due_date"] < today_str and t["status"] != "completed"
        due_str = ""
        if t["due_date"]:
            formatted_due = format_display_date(t["due_date"])
            if is_overdue:
                due_str = f'<span class="icon-text-pair"><span class="emoji-icon">⚠️</span><span class="task-due">Due: {formatted_due}</span></span>'
            else:
                due_str = f'<span class="task-due">Due: {formatted_due}</span>'
        desc_str = (
            f'<div class="task-desc">{t["description"]}</div>'
            if t["description"]
            else ""
        )
        tag_str = (
            f'<span class="task-tag {tag_class}">{t["tag"]}</span>' if t["tag"] else ""
        )
        source_str = (
            f'<span class="task-source">via {t["source"]}</span>' if t["source"] and t["source"] != "manual" else ""
        )

        html += f"""
        <div class="task-item">
            <div class="task-checkbox-container">
                <input type="checkbox" class="task-checkbox" {checked}
                       hx-post="/tasks/{t["id"]}/toggle"
                       hx-swap="none">
                <div class="task-content">
                    <div class="task-title">{t["title"]}</div>
                    {desc_str}
                    <div class="task-meta">
                        {tag_str}
                        {due_str}
                        {source_str}
                    </div>
                </div>
            </div>
            <button class="btn-delete"
                    hx-delete="/tasks/{t["id"]}"
                    hx-swap="outerHTML"
                    hx-target="closest .task-item"
                    hx-confirm="Are you sure you want to delete this task?">🗑️</button>
        </div>
        """
    return HTMLResponse(content=html)


@app.post("/tasks/{task_id}/toggle")
async def toggle_task(task_id: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        task_row = cursor.fetchone()
        if not task_row:
            conn.close()
            raise HTTPException(status_code=404, detail="Task not found")

        if task_row["status"] == "completed":
            # Toggling back to open (undo action)
            cursor.execute(
                "UPDATE tasks SET status = 'open', completed_at = NULL WHERE id = ?",
                (task_id,),
            )
            # Delete the child recurring task if it is still open
            cursor.execute(
                "DELETE FROM tasks WHERE parent_task_id = ? AND status = 'open'",
                (task_id,),
            )
        else:
            # Toggling to completed
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                "UPDATE tasks SET status = 'completed', completed_at = ? WHERE id = ?",
                (now_str, task_id),
            )
            # Advance recurrence
            if task_row["recurrence"] and task_row["recurrence"].lower() in [
                "daily",
                "weekly",
                "biweekly",
                "monthly",
            ]:
                advance_recurring_task(cursor, task_row)

        conn.commit()
        conn.close()

        headers = {"HX-Trigger": "refresh-dashboard"}
        return HTMLResponse(content="", headers=headers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/dashboard/tasks", response_class=HTMLResponse)
async def get_dashboard_tasks():
    try:
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        conn = get_readonly_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM tasks WHERE status = 'open' AND (due_date <= ? OR due_date IS NULL) ORDER BY due_date ASC, id DESC",
            (today_str,),
        )
        tasks = cursor.fetchall()
        conn.close()
    except Exception as e:
        return HTMLResponse(
            content=f"<div style='color: var(--accent-red)'>Error: {e}</div>"
        )

    html = ""
    if not tasks:
        return HTMLResponse(
            content="<div style='color: var(--text-muted); font-size: 14px; font-style: italic;'>No open or overdue tasks.</div>"
        )

    for t in tasks:
        checked = "checked" if t["status"] == "completed" else ""
        tag_class = t["tag"] if t["tag"] else ""
        is_overdue = t["due_date"] is not None and t["due_date"] < today_str
        due_str = ""
        if t["due_date"]:
            formatted_due = format_display_date(t["due_date"])
            if is_overdue:
                due_str = f'<span class="icon-text-pair"><span class="emoji-icon">⚠️</span><span class="task-due">Due: {formatted_due}</span></span>'
            else:
                due_str = f'<span class="task-due">Due: {formatted_due}</span>'
        desc_str = (
            f'<div class="task-desc">{t["description"]}</div>'
            if t["description"]
            else ""
        )
        tag_str = (
            f'<span class="task-tag {tag_class}">{t["tag"]}</span>' if t["tag"] else ""
        )
        source_str = (
            f'<span class="task-source">via {t["source"]}</span>' if t["source"] and t["source"] != "manual" else ""
        )

        html += f"""
        <div class="task-item">
            <div class="task-checkbox-container">
                <input type="checkbox" class="task-checkbox" {checked}
                       hx-post="/tasks/{t["id"]}/toggle"
                       hx-swap="none">
                <div class="task-content">
                    <div class="task-title">{t["title"]}</div>
                    {desc_str}
                    <div class="task-meta">
                        {tag_str}
                        {due_str}
                        {source_str}
                    </div>
                </div>
            </div>
            <button class="btn-delete"
                    hx-delete="/tasks/{t["id"]}"
                    hx-swap="outerHTML"
                    hx-target="closest .task-item"
                    hx-confirm="Are you sure you want to delete this task?">🗑️</button>
        </div>
        """
    return HTMLResponse(content=html)


@app.get("/dashboard/habits", response_class=HTMLResponse)
async def get_dashboard_habits():
    try:
        streaks_data = get_habit_streaks()
    except Exception as e:
        return HTMLResponse(
            content=f"<div style='color: var(--accent-red)'>Error: {e}</div>"
        )

    if streaks_data.get("status") == "error":
        return HTMLResponse(
            content=f"<div style='color: var(--accent-red)'>Error: {streaks_data.get('message')}</div>"
        )

    today = datetime.date.today()
    uncompleted_habits = []
    for name, data in streaks_data["streaks"].items():
        # Parse created_at to a date
        created_at_str = data.get("created_at") or ""
        if " " in created_at_str:
            created_at_str = created_at_str.split(" ")[0]
        try:
            created_date = datetime.datetime.strptime(created_at_str, "%Y-%m-%d").date()
        except Exception:
            created_date = datetime.date.min

        freq = data["frequency"].lower().strip()
        current_period = get_period_start(today, freq, created_date)

        completed = False
        last_logged_str = data.get("last_logged")
        if last_logged_str:
            try:
                last_logged_date = datetime.datetime.strptime(last_logged_str, "%Y-%m-%d").date()
                last_logged_period = get_period_start(last_logged_date, freq, created_date)
                if last_logged_period == current_period:
                    completed = True
            except Exception:
                pass

        if not completed:
            uncompleted_habits.append((name, data))

    if not uncompleted_habits:
        return HTMLResponse(
            content="<div style='color: var(--primary); font-size: 14px; font-style: italic;'>All habits completed for today! 🔥</div>"
        )

    html = ""
    for name, data in uncompleted_habits:
        habit_id = data["habit_id"]
        btn_attr = (
            f'class="btn-log-habit" hx-post="/habits/{habit_id}/log" hx-swap="none"'
        )
        streak_unit = data.get("streak_unit", "day")
        html += f"""
        <div class="habit-item">
            <div class="habit-info">
                <div class="habit-name">{name}</div>
                <div class="habit-desc">{data["frequency"]}</div>
                <div class="habit-streak"><span class="icon-text-pair"><span class="emoji-icon">🔥</span><span>{data["current_streak"]} {streak_unit} streak</span></span></div>
            </div>
            <button {btn_attr}>Log Today</button>
        </div>
        """
    return HTMLResponse(content=html)


@app.delete("/tasks/{task_id}")
async def delete_task(task_id: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        conn.close()

        headers = {"HX-Trigger": "refresh-dashboard"}
        return HTMLResponse(content="", headers=headers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


def get_exercise_progress(exercise_name: str) -> dict:
    """Queries database to find progress (earliest vs. latest session weight) for an exercise.

    Parses sets JSON for the earliest and latest entry, taking the max weight_kg in each session.
    """
    try:
        conn = get_readonly_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT sets, date FROM workout_logs WHERE exercise = ? ORDER BY date ASC, id ASC",
            (exercise_name,),
        )
        logs = cursor.fetchall()
        conn.close()
    except Exception:
        logs = []

    if not logs:
        return {
            "exercise_name": exercise_name,
            "first_weight": "Not yet logged",
            "current_weight": "Not yet logged",
        }

    def get_max_weight(sets_str: str) -> float | None:
        try:
            sets = json.loads(sets_str)
            if not isinstance(sets, list) or not sets:
                return None
            weights = [
                float(s["weight_kg"])
                for s in sets
                if isinstance(s, dict)
                and "weight_kg" in s
                and s["weight_kg"] is not None
            ]
            return max(weights) if weights else None
        except Exception:
            return None

    first_weight = get_max_weight(logs[0]["sets"])
    current_weight = get_max_weight(logs[-1]["sets"])

    if first_weight is None:
        first_weight_str = "Not yet logged"
    elif first_weight == 0:
        first_weight_str = "Bodyweight"
    else:
        first_weight_str = f"{first_weight} kg"

    if current_weight is None:
        current_weight_str = "Not yet logged"
    elif current_weight == 0:
        current_weight_str = "Bodyweight"
    else:
        current_weight_str = f"{current_weight} kg"

    return {
        "exercise_name": exercise_name,
        "first_weight": first_weight_str,
        "current_weight": current_weight_str,
    }


@app.get("/workouts/lifts", response_class=HTMLResponse)
async def get_workouts_lifts():
    try:
        conn = get_readonly_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT exercise_name FROM plan_exercises WHERE active = 1 ORDER BY exercise_name ASC"
        )
        rows = cursor.fetchall()
        conn.close()
    except Exception as e:
        return HTMLResponse(
            content=f"<div style='color: var(--accent-red)'>Error: {e}</div>"
        )

    if not rows:
        return HTMLResponse(
            content="<div style='color: var(--text-muted); font-size: 14px; font-style: italic;'>No exercises in your active plan yet.</div>"
        )

    lifts_html = ""
    for r in rows:
        ex_name = r["exercise_name"]
        progress = get_exercise_progress(ex_name)
        lifts_html += f"""
        <tr>
            <td style="font-weight: 500; color: var(--text-primary);">{progress["exercise_name"]}</td>
            <td style="color: var(--primary);">{progress["first_weight"]}</td>
            <td style="color: var(--primary); font-weight: 600;">{progress["current_weight"]}</td>
        </tr>
        """

    html = f"""
    <table>
        <thead>
            <tr>
                <th>Exercise</th>
                <th>First Weight</th>
                <th>Current Weight</th>
            </tr>
        </thead>
        <tbody>
            {lifts_html}
        </tbody>
    </table>
    """
    return HTMLResponse(content=html)


@app.get("/workouts", response_class=HTMLResponse)
async def get_workouts_section(request: Request):
    return await render_section(request, "workouts", get_workouts_section_html())


@app.get("/workouts/items", response_class=HTMLResponse)
async def get_workouts_items():
    try:
        conn = get_readonly_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM workout_logs ORDER BY date DESC, id DESC")
        workouts = cursor.fetchall()
        conn.close()
    except Exception as e:
        return HTMLResponse(
            content=f"<div style='color: var(--accent-red)'>Error: {e}</div>"
        )

    import itertools

    html = ""
    if not workouts:
        html = "<div style='color: var(--text-muted); font-size: 14px; font-style: italic;'>No workouts logged yet.</div>"
    else:
        for date, group in itertools.groupby(workouts, key=lambda w: w["date"]):
            formatted_date = format_display_date(date, with_weekday=True)
            items_html = ""
            for w in group:
                try:
                    sets_data = json.loads(w["sets"])
                except Exception:
                    sets_data = []

                sets_html = ""
                for idx, s in enumerate(sets_data):
                    weight = s.get("weight_kg")
                    if not weight or weight == 0:
                        sets_html += f'<span class="workout-set-badge">Set {idx + 1}: {s["reps"]}r</span>'
                    else:
                        sets_html += f'<span class="workout-set-badge">Set {idx + 1}: {s["reps"]}r @ {weight}kg</span>'

                notes_html = (
                    f'<div class="workout-notes">{w["notes"]}</div>' if w["notes"] else ""
                )

                items_html += f"""
                <div class="workout-item">
                    <div class="workout-header">
                        <div class="workout-exercise">{w["exercise"]}</div>
                        <button class="btn-delete"
                                hx-delete="/workouts/{w["id"]}"
                                hx-swap="outerHTML"
                                hx-target="closest .workout-item"
                                hx-confirm="Are you sure you want to delete this workout log?">🗑️</button>
                    </div>
                    <div class="workout-sets">
                        {sets_html}
                    </div>
                    {notes_html}
                </div>
                """

            html += f"""
            <div class="workout-session-card" hx-on::after-swap="if (this.querySelector('.workout-session-entries').children.length === 0) {{ this.remove(); }}">
                <div class="workout-session-header">
                    <div class="workout-session-date">{formatted_date}</div>
                </div>
                <div class="workout-session-entries">
                    {items_html}
                </div>
            </div>
            """
    return HTMLResponse(content=html)


@app.delete("/workouts/{workout_id}")
async def delete_workout(workout_id: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM workout_logs WHERE id = ?", (workout_id,))
        conn.commit()
        conn.close()

        headers = {"HX-Trigger": "refresh-dashboard"}
        return HTMLResponse(content="", headers=headers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/habits", response_class=HTMLResponse)
async def get_habits_section(request: Request):
    return await render_section(request, "habits", get_habits_section_html())


@app.get("/habits/items", response_class=HTMLResponse)
async def get_habits_items():
    try:
        streaks_data = get_habit_streaks()
    except Exception as e:
        return HTMLResponse(
            content=f"<div style='color: var(--accent-red)'>Error: {e}</div>"
        )

    html = ""
    if streaks_data.get("status") == "error":
        return HTMLResponse(
            content=f"<div style='color: var(--accent-red)'>Error: {streaks_data.get('message')}</div>"
        )

    today = datetime.date.today()
    monday_current = today - datetime.timedelta(days=today.weekday())
    monday_oldest = monday_current - datetime.timedelta(weeks=11)

    for name, data in streaks_data["streaks"].items():
        habit_id = data["habit_id"]

        # Parse habit created_at date
        created_at_str = data.get("created_at") or ""
        if " " in created_at_str:
            created_at_str = created_at_str.split(" ")[0]
        try:
            created_date = datetime.datetime.strptime(created_at_str, "%Y-%m-%d").date()
        except Exception:
            created_date = datetime.date.min

        freq = data["frequency"].lower().strip()
        current_period = get_period_start(today, freq, created_date)

        completed = False
        last_logged_str = data.get("last_logged")
        if last_logged_str:
            try:
                last_logged_date = datetime.datetime.strptime(last_logged_str, "%Y-%m-%d").date()
                last_logged_period = get_period_start(last_logged_date, freq, created_date)
                if last_logged_period == current_period:
                    completed = True
            except Exception:
                pass

        btn_attr = (
            'class="btn-log-habit completed" disabled'
            if completed
            else f'class="btn-log-habit" hx-post="/habits/{habit_id}/log" hx-swap="none"'
        )
        btn_text = "Completed" if completed else "Log Today"

        # Generate heatmap HTML
        freq = data["frequency"].lower().strip()
        heatmap_html = ""
        if freq == "daily":
            day_cells = []
            for i in range(84):
                cell_date = monday_oldest + datetime.timedelta(days=i)
                cell_date = get_period_start(cell_date, "daily")
                formatted_date = format_display_date(cell_date)
                date_str = cell_date.strftime("%Y-%m-%d")

                is_pre = cell_date < created_date
                is_post = cell_date > today

                if is_post:
                    day_cells.append(f'<span class="heatmap-cell state-na" title="{formatted_date}"></span>')
                elif date_str in data.get("completed_dates", []):
                    day_cells.append(f'<span class="heatmap-cell state-completed" title="{formatted_date}"></span>')
                elif is_pre:
                    day_cells.append(f'<span class="heatmap-cell state-na" title="{formatted_date}"></span>')
                else:
                    day_cells.append(f'<span class="heatmap-cell state-missed" title="{formatted_date}"></span>')

            heatmap_html = f'<div class="habit-heatmap daily">{"".join(day_cells)}</div>'
        elif freq == "weekly":
            week_cells = []
            for c in range(12):
                week_start = monday_oldest + datetime.timedelta(weeks=c)
                week_start = get_period_start(week_start, "weekly")
                week_end = week_start + datetime.timedelta(days=6)

                is_pre = week_end < created_date
                is_post = week_start > today

                formatted_date = format_display_date(week_start)

                completed_in_week = False
                for log_date_str in data.get("completed_dates", []):
                    try:
                        log_date = datetime.datetime.strptime(log_date_str, "%Y-%m-%d").date()
                        if week_start <= log_date <= week_end:
                            completed_in_week = True
                            break
                    except Exception:
                        continue

                if is_post:
                    week_cells.append(f'<span class="heatmap-cell state-na" title="{formatted_date}"></span>')
                elif completed_in_week:
                    week_cells.append(f'<span class="heatmap-cell state-completed" title="{formatted_date}"></span>')
                elif is_pre:
                    week_cells.append(f'<span class="heatmap-cell state-na" title="{formatted_date}"></span>')
                else:
                    week_cells.append(f'<span class="heatmap-cell state-missed" title="{formatted_date}"></span>')

            heatmap_html = f'<div class="habit-heatmap weekly">{"".join(week_cells)}</div>'
        elif freq == "biweekly":
            biweekly_cells = []
            current_period_start = get_period_start(today, "biweekly", created_date)
            for c in range(6):
                period_start = current_period_start - datetime.timedelta(days=(5 - c) * 14)
                period_start = get_period_start(period_start, "biweekly", created_date)
                period_end = period_start + datetime.timedelta(days=13)

                is_pre = period_end < created_date
                is_post = period_start > today

                formatted_date = format_display_date(period_start)

                completed_in_period = False
                for log_date_str in data.get("completed_dates", []):
                    try:
                        log_date = datetime.datetime.strptime(log_date_str, "%Y-%m-%d").date()
                        if period_start <= log_date <= period_end:
                            completed_in_period = True
                            break
                    except Exception:
                        continue

                if is_post:
                    biweekly_cells.append(f'<span class="heatmap-cell state-na" title="{formatted_date}"></span>')
                elif completed_in_period:
                    biweekly_cells.append(f'<span class="heatmap-cell state-completed" title="{formatted_date}"></span>')
                elif is_pre:
                    biweekly_cells.append(f'<span class="heatmap-cell state-na" title="{formatted_date}"></span>')
                else:
                    biweekly_cells.append(f'<span class="heatmap-cell state-missed" title="{formatted_date}"></span>')

            heatmap_html = f'<div class="habit-heatmap weekly">{"".join(biweekly_cells)}</div>'
        elif freq == "monthly":
            monthly_cells = []
            current_month_start = get_period_start(today, "monthly")
            for c in range(12):
                month_start = get_month_start_relative(current_month_start, c - 11)
                month_start = get_period_start(month_start, "monthly")
                next_month_start = get_month_start_relative(month_start, 1)
                month_end = next_month_start - datetime.timedelta(days=1)

                is_pre = month_end < created_date
                is_post = month_start > today

                formatted_date = format_display_date(month_start)

                completed_in_month = False
                for log_date_str in data.get("completed_dates", []):
                    try:
                        log_date = datetime.datetime.strptime(log_date_str, "%Y-%m-%d").date()
                        if month_start <= log_date <= month_end:
                            completed_in_month = True
                            break
                    except Exception:
                        continue

                if is_post:
                    monthly_cells.append(f'<span class="heatmap-cell state-na" title="{formatted_date}"></span>')
                elif completed_in_month:
                    monthly_cells.append(f'<span class="heatmap-cell state-completed" title="{formatted_date}"></span>')
                elif is_pre:
                    monthly_cells.append(f'<span class="heatmap-cell state-na" title="{formatted_date}"></span>')
                else:
                    monthly_cells.append(f'<span class="heatmap-cell state-missed" title="{formatted_date}"></span>')

            heatmap_html = f'<div class="habit-heatmap weekly">{"".join(monthly_cells)}</div>'

        streak_unit = data.get("streak_unit", "day")
        html += f"""
        <div class="habit-item">
            <div class="habit-info">
                <div class="habit-name">{name}</div>
                <div class="habit-desc">{data["frequency"]}</div>
                <div class="habit-streak"><span class="icon-text-pair"><span class="emoji-icon">🔥</span><span>{data["current_streak"]} {streak_unit} streak</span></span></div>
                {heatmap_html}
            </div>
            <button {btn_attr}>{btn_text}</button>
        </div>
        """
    return HTMLResponse(content=html)


@app.post("/habits/{habit_id}/log")
async def log_habit_endpoint(habit_id: int):
    try:
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO habit_logs (habit_id, date, status) VALUES (?, ?, 'completed')",
            (habit_id, today_str),
        )
        conn.commit()
        conn.close()

        headers = {"HX-Trigger": "refresh-dashboard"}
        return HTMLResponse(content="", headers=headers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/calendar", response_class=HTMLResponse)
async def calendar_section(request: Request):
    return await render_section(request, "calendar", get_calendar_section_html())


@app.get("/calendar/items", response_class=HTMLResponse)
async def get_calendar_items():
    try:
        today = datetime.date.today()
        start_date = (today - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
        end_date = (today + datetime.timedelta(days=56)).strftime("%Y-%m-%d")
        
        cal_data = get_calendar_events_range(start_date, end_date)
        if cal_data.get("status") == "error":
            raise Exception(cal_data.get("message", "Unknown error fetching calendar events"))
        events = cal_data.get("events", [])
    except Exception as e:
        return HTMLResponse(
            content=f"<div style='color: var(--accent-red)'>Error: {e}</div>"
        )
    return HTMLResponse(content=render_calendar_events_html(events, show_date=True))


@app.get("/calendar/today", response_class=HTMLResponse)
async def get_calendar_today():
    try:
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        cal_data = get_calendar_events(today_str)
        if cal_data.get("status") == "error":
            raise Exception(cal_data.get("message", "Unknown error fetching calendar events"))
        events = cal_data.get("events", [])
        
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        original_count = len(events)
        filtered_events = [e for e in events if e.get("end_time") and e["end_time"] >= now_str]
        
        if original_count > 0 and len(filtered_events) == 0:
            empty_msg = "All done for today."
        else:
            empty_msg = "No events scheduled."
    except Exception as e:
        return HTMLResponse(
            content=f"<div style='color: var(--accent-red)'>Error: {e}</div>"
        )
    return HTMLResponse(content=render_calendar_events_html(filtered_events, show_date=False, empty_message=empty_msg))


@app.post("/chat", response_class=HTMLResponse)
async def chat_endpoint(message: str = Form(...)):
    new_msg = types.Content(role="user", parts=[types.Part(text=message)])
    agent_response = ""

    try:
        # Ensure session exists in the session service
        session = await runner.session_service.get_session(
            app_name="app", user_id="default-user", session_id="default-session"
        )
        if session is None:
            await runner.session_service.create_session(
                app_name="app", user_id="default-user", session_id="default-session"
            )

        async for event in runner.run_async(
            user_id="default-user", session_id="default-session", new_message=new_msg
        ):
            if event.author == "root_agent" and event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        agent_response += part.text
    except Exception as e:
        agent_response = f"**Error running agent:** {e}"

    # Render markdown to HTML
    agent_html = markdown.markdown(agent_response, extensions=["tables", "fenced_code"])

    response_html = f"""
    <div class="message-bubble message-agent">{agent_html}</div>
    """

    headers = {"HX-Trigger": "refresh-dashboard"}
    return HTMLResponse(content=response_html, headers=headers)
