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
