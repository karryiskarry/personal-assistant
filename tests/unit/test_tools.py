import datetime

from app.db import get_db_connection
from app.tools import create_task


def test_create_task_default_due_date():
    # Insert a task without a due date
    res = create_task(
        title="Test Task Default Due Date",
        description="This is a test task to verify default due date.",
        source="test_runner",
    )
    assert res["status"] == "success"

    # Verify the due date in the database is the current date
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT due_date FROM tasks WHERE title = 'Test Task Default Due Date' ORDER BY id DESC LIMIT 1"
    )
    row = cursor.fetchone()

    # Clean up the test task
    cursor.execute("DELETE FROM tasks WHERE title = 'Test Task Default Due Date'")
    conn.commit()
    conn.close()

    assert row is not None
    expected_today = datetime.date.today().strftime("%Y-%m-%d")
    assert row["due_date"] == expected_today


def test_set_exercise_active():
    from app.tools import set_exercise_active

    # Test insert active
    res = set_exercise_active("Test Bench Press", True)
    assert res["status"] == "success"

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT active FROM plan_exercises WHERE exercise_name = 'Test Bench Press'"
    )
    row = cursor.fetchone()
    assert row is not None
    assert row["active"] == 1

    # Test update inactive
    res = set_exercise_active("Test Bench Press", False)
    assert res["status"] == "success"
    cursor.execute(
        "SELECT active FROM plan_exercises WHERE exercise_name = 'Test Bench Press'"
    )
    row = cursor.fetchone()
    assert row is not None
    assert row["active"] == 0

    # Cleanup
    cursor.execute(
        "DELETE FROM plan_exercises WHERE exercise_name = 'Test Bench Press'"
    )
    conn.commit()
    conn.close()


def test_sync_active_exercises():
    from app.tools import set_exercise_active, sync_active_exercises

    # Set up initial state
    set_exercise_active("Test Exercise A", True)
    set_exercise_active("Test Exercise B", True)

    # Sync to new list: B and C should be active, A should be deactivated
    res = sync_active_exercises(["Test Exercise B", "Test Exercise C"])
    assert res["status"] == "success"

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check A
    cursor.execute(
        "SELECT active FROM plan_exercises WHERE exercise_name = 'Test Exercise A'"
    )
    row_a = cursor.fetchone()
    assert row_a is not None
    assert row_a["active"] == 0

    # Check B
    cursor.execute(
        "SELECT active FROM plan_exercises WHERE exercise_name = 'Test Exercise B'"
    )
    row_b = cursor.fetchone()
    assert row_b is not None
    assert row_b["active"] == 1

    # Check C
    cursor.execute(
        "SELECT active FROM plan_exercises WHERE exercise_name = 'Test Exercise C'"
    )
    row_c = cursor.fetchone()
    assert row_c is not None
    assert row_c["active"] == 1

    # Cleanup
    cursor.execute(
        "DELETE FROM plan_exercises WHERE exercise_name IN ('Test Exercise A', 'Test Exercise B', 'Test Exercise C')"
    )
    conn.commit()
    conn.close()


def test_get_exercise_progress():
    import json

    from app.main import get_exercise_progress

    conn = get_db_connection()
    cursor = conn.cursor()

    # Seed logs
    cursor.execute(
        "INSERT INTO workout_logs (exercise, sets, date, notes) VALUES (?, ?, ?, ?)",
        (
            "Test Progress Ex",
            json.dumps(
                [{"reps": 5, "weight_kg": 50.0}, {"reps": 5, "weight_kg": 55.0}]
            ),
            "2026-06-01",
            "",
        ),
    )
    cursor.execute(
        "INSERT INTO workout_logs (exercise, sets, date, notes) VALUES (?, ?, ?, ?)",
        (
            "Test Progress Ex",
            json.dumps(
                [{"reps": 5, "weight_kg": 60.0}, {"reps": 5, "weight_kg": 65.0}]
            ),
            "2026-06-15",
            "",
        ),
    )
    conn.commit()

    # Get progress
    prog = get_exercise_progress("Test Progress Ex")
    assert prog["exercise_name"] == "Test Progress Ex"
    assert prog["first_weight"] == "55.0 kg"
    assert prog["current_weight"] == "65.0 kg"

    # Cleanup
    cursor.execute("DELETE FROM workout_logs WHERE exercise = 'Test Progress Ex'")
    conn.commit()
    conn.close()


def test_create_habit():
    from app.tools import create_habit

    # --- Happy path: daily habit with description ---
    res = create_habit(
        name="Test Flossing",
        frequency="daily",
        description="Floss every night before bed",
    )
    assert res["status"] == "success"
    assert "habit_id" in res
    habit_id = res["habit_id"]

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM habits WHERE id = ?", (habit_id,))
    row = cursor.fetchone()

    assert row is not None
    assert row["name"] == "Test Flossing"
    assert row["frequency"] == "daily"
    assert row["description"] == "Floss every night before bed"

    # --- Happy path: weekly habit, no description ---
    res2 = create_habit(name="Test Weekly Run", frequency="weekly")
    assert res2["status"] == "success"
    habit_id2 = res2["habit_id"]

    cursor.execute(
        "SELECT frequency, description FROM habits WHERE id = ?", (habit_id2,)
    )
    row2 = cursor.fetchone()
    assert row2["frequency"] == "weekly"
    assert row2["description"] is None

    # --- Sad path: invalid frequency ---
    res3 = create_habit(name="Bad Habit", frequency="hourly")
    assert res3["status"] == "error"
    assert "frequency" in res3["message"].lower()

    # Cleanup
    cursor.execute("DELETE FROM habits WHERE id IN (?, ?)", (habit_id, habit_id2))
    conn.commit()
    conn.close()


def test_sync_active_exercises_empty_guard():
    from app.tools import sync_active_exercises
    res = sync_active_exercises([])
    assert res["status"] == "error"
    assert "cannot be called with an empty list" in res["message"]


def test_get_habit_streaks_heatmap_data():
    import datetime

    from app.tools import get_db_connection, get_habit_streaks

    # Setup database with test habit and logs
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create habit created 20 days ago
    created_at_date = (datetime.date.today() - datetime.timedelta(days=20)).strftime("%Y-%m-%d 00:00:00")
    cursor.execute(
        "INSERT INTO habits (name, frequency, created_at) VALUES ('Heatmap Test Habit', 'daily', ?)",
        (created_at_date,)
    )
    habit_id = cursor.lastrowid

    # Log completion 10 days ago (in-range, post-creation)
    date_in_range = (datetime.date.today() - datetime.timedelta(days=10)).strftime("%Y-%m-%d")
    cursor.execute(
        "INSERT INTO habit_logs (habit_id, date, status) VALUES (?, ?, 'completed')",
        (habit_id, date_in_range)
    )

    # Log completion 30 days ago (in 12-week window, but pre-creation)
    date_before_creation = (datetime.date.today() - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    cursor.execute(
        "INSERT INTO habit_logs (habit_id, date, status) VALUES (?, ?, 'completed')",
        (habit_id, date_before_creation)
    )

    conn.commit()

    # Fetch streaks data
    res = get_habit_streaks()
    assert res["status"] == "success"
    assert "Heatmap Test Habit" in res["streaks"]

    h_data = res["streaks"]["Heatmap Test Habit"]
    assert h_data["created_at"] == created_at_date
    assert date_in_range in h_data["completed_dates"]
    assert date_before_creation in h_data["completed_dates"]

    # Verify that the log date 30 days ago is indeed before the created_at date
    created_dt = datetime.datetime.strptime(created_at_date.split(" ")[0], "%Y-%m-%d").date()
    log_before_dt = datetime.datetime.strptime(date_before_creation, "%Y-%m-%d").date()
    assert log_before_dt < created_dt

    # Cleanup
    cursor.execute("DELETE FROM habit_logs WHERE habit_id = ?", (habit_id,))
    cursor.execute("DELETE FROM habits WHERE id = ?", (habit_id,))
    conn.commit()
    conn.close()


def test_get_period_start_frequencies():
    import datetime

    from app.tools import get_period_start

    anchor = datetime.date(2026, 6, 9)  # Tuesday
    # Daily
    dt = datetime.date(2026, 6, 24)
    assert get_period_start(dt, "daily") == dt

    # Weekly (2026-06-24 is Wednesday, Monday is 2026-06-22)
    assert get_period_start(dt, "weekly") == datetime.date(2026, 6, 22)

    # Biweekly: (24 - 9) = 15 days. 15 // 14 = 1. anchor + 14 = 2026-06-23
    assert get_period_start(dt, "biweekly", anchor) == datetime.date(2026, 6, 23)

    # Monthly
    assert get_period_start(dt, "monthly") == datetime.date(2026, 6, 1)


def test_streak_calculation_biweekly_monthly():
    import datetime

    from app.tools import get_db_connection, get_habit_streaks

    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Biweekly habit with grace period
    # Created 40 days ago
    today = datetime.date.today()
    created_at_biweekly = (today - datetime.timedelta(days=40)).strftime("%Y-%m-%d 00:00:00")
    cursor.execute(
        "INSERT INTO habits (name, frequency, created_at) VALUES ('Biweekly Streak Habit', 'biweekly', ?)",
        (created_at_biweekly,)
    )
    biweekly_id = cursor.lastrowid

    # We want a streak of 2 periods with grace period.
    # Today's period: current_period. Let's make it have no log.
    # Immediately preceding period: has a log.
    # The one before that: has a log.
    created_dt = (today - datetime.timedelta(days=40))
    idx = (today - created_dt).days // 14
    current_period_start = created_dt + datetime.timedelta(days=idx * 14)

    prev_period_start = current_period_start - datetime.timedelta(days=14)
    prev_prev_period_start = prev_period_start - datetime.timedelta(days=14)

    # Log in prev_period and prev_prev_period
    cursor.execute(
        "INSERT INTO habit_logs (habit_id, date, status) VALUES (?, ?, 'completed')",
        (biweekly_id, prev_period_start.strftime("%Y-%m-%d"))
    )
    cursor.execute(
        "INSERT INTO habit_logs (habit_id, date, status) VALUES (?, ?, 'completed')",
        (biweekly_id, prev_prev_period_start.strftime("%Y-%m-%d"))
    )

    # 2. Monthly habit with broken streak
    created_at_monthly = (today - datetime.timedelta(days=120)).strftime("%Y-%m-%d 00:00:00")
    cursor.execute(
        "INSERT INTO habits (name, frequency, created_at) VALUES ('Monthly Streak Habit', 'monthly', ?)",
        (created_at_monthly,)
    )
    monthly_id = cursor.lastrowid

    # Log in current month, skip previous month, log in the month before that
    current_month_start = today.replace(day=1)
    prev_month_start = (current_month_start - datetime.timedelta(days=1)).replace(day=1)
    prev_prev_month_start = (prev_month_start - datetime.timedelta(days=1)).replace(day=1)

    cursor.execute(
        "INSERT INTO habit_logs (habit_id, date, status) VALUES (?, ?, 'completed')",
        (monthly_id, current_month_start.strftime("%Y-%m-%d"))
    )
    cursor.execute(
        "INSERT INTO habit_logs (habit_id, date, status) VALUES (?, ?, 'completed')",
        (monthly_id, prev_prev_month_start.strftime("%Y-%m-%d"))
    )

    conn.commit()

    try:
        streaks = get_habit_streaks()
        assert streaks["status"] == "success"

        # Verify Biweekly (grace period applied: current period has no log, but prev two do -> streak = 2)
        b_data = streaks["streaks"]["Biweekly Streak Habit"]
        assert b_data["current_streak"] == 2
        assert b_data["streak_unit"] == "biweekly"

        # Verify Monthly (broken streak: logged in current, but not prev -> streak = 1)
        m_data = streaks["streaks"]["Monthly Streak Habit"]
        assert m_data["current_streak"] == 1
        assert m_data["streak_unit"] == "month"

    finally:
        cursor.execute("DELETE FROM habit_logs WHERE habit_id IN (?, ?)", (biweekly_id, monthly_id))
        cursor.execute("DELETE FROM habits WHERE id IN (?, ?)", (biweekly_id, monthly_id))
        conn.commit()
        conn.close()


def test_heatmap_query_window():
    import datetime

    from app.tools import get_db_connection, get_habit_streaks

    conn = get_db_connection()
    cursor = conn.cursor()
    today = datetime.date.today()

    # Create monthly habit
    cursor.execute(
        "INSERT INTO habits (name, frequency, created_at) VALUES ('Monthly Heatmap Habit', 'monthly', ?)",
        ((today - datetime.timedelta(days=200)).strftime("%Y-%m-%d 00:00:00"),)
    )
    monthly_id = cursor.lastrowid

    # Create daily habit
    cursor.execute(
        "INSERT INTO habits (name, frequency, created_at) VALUES ('Daily Heatmap Habit', 'daily', ?)",
        ((today - datetime.timedelta(days=200)).strftime("%Y-%m-%d 00:00:00"),)
    )
    daily_id = cursor.lastrowid

    # Log 100 days ago (in 365-day monthly window, but not in 84-day daily window)
    date_100_ago = (today - datetime.timedelta(days=100)).strftime("%Y-%m-%d")
    cursor.execute(
        "INSERT INTO habit_logs (habit_id, date, status) VALUES (?, ?, 'completed')",
        (monthly_id, date_100_ago)
    )
    cursor.execute(
        "INSERT INTO habit_logs (habit_id, date, status) VALUES (?, ?, 'completed')",
        (daily_id, date_100_ago)
    )

    conn.commit()

    try:
        streaks = get_habit_streaks()
        assert streaks["status"] == "success"

        m_data = streaks["streaks"]["Monthly Heatmap Habit"]
        d_data = streaks["streaks"]["Daily Heatmap Habit"]

        # 100 days ago should be in monthly's completed_dates, but NOT daily's
        assert date_100_ago in m_data["completed_dates"]
        assert date_100_ago not in d_data["completed_dates"]

    finally:
        cursor.execute("DELETE FROM habit_logs WHERE habit_id IN (?, ?)", (monthly_id, daily_id))
        cursor.execute("DELETE FROM habits WHERE id IN (?, ?)", (monthly_id, daily_id))
        conn.commit()
        conn.close()


def test_resolve_weekday_date():
    import datetime
    import pytest
    from app.tools import resolve_weekday_date

    # Verify that resolving works case-insensitively
    res_sat = resolve_weekday_date("saturday")
    assert res_sat["weekday"] == "Saturday"
    dt_sat = datetime.datetime.strptime(res_sat["date"], "%Y-%m-%d")
    assert dt_sat.weekday() == 5

    res_mon = resolve_weekday_date("  MONDAY  ")
    assert res_mon["weekday"] == "Monday"
    dt_mon = datetime.datetime.strptime(res_mon["date"], "%Y-%m-%d")
    assert dt_mon.weekday() == 0

    # Test error cases
    with pytest.raises(ValueError):
        resolve_weekday_date("Funday")




