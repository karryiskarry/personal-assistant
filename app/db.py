import json
import os
import sqlite3
from datetime import datetime, timedelta

_DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "personal_assistant.db"
)
DB_PATH: str = os.environ.get("PERSONAL_ASSISTANT_DB_PATH", _DEFAULT_DB_PATH)


def get_db_connection():
    """Returns a SQLite connection to the database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_readonly_db_connection():
    """Returns a read-only SQLite connection to the database."""
    # Construct an absolute file URI for read-only mode
    db_uri = f"file:{os.path.abspath(DB_PATH)}?mode=ro"
    conn = sqlite3.connect(db_uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes database tables if they do not exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create tasks table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            due_date TEXT, -- YYYY-MM-DD
            recurrence TEXT, -- 'daily', 'weekly', 'biweekly', 'monthly', or NULL
            status TEXT DEFAULT 'open', -- 'open', 'completed'
            tag TEXT, -- 'chore', 'work', 'health', etc.
            source TEXT DEFAULT 'manual', -- 'manual', 'nl_capture', 'plan_generated'
            parent_task_id INTEGER,
            completed_at TEXT, -- YYYY-MM-DD HH:MM:SS
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (parent_task_id) REFERENCES tasks(id) ON DELETE SET NULL
        )
    """)

    # Create habits table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS habits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            frequency TEXT DEFAULT 'daily', -- 'daily', 'weekly'
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create habit_logs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS habit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            habit_id INTEGER NOT NULL,
            date TEXT NOT NULL, -- YYYY-MM-DD
            status TEXT DEFAULT 'completed',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (habit_id) REFERENCES habits(id) ON DELETE CASCADE,
            UNIQUE(habit_id, date)
        )
    """)

    # Create workout_logs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workout_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exercise TEXT NOT NULL,
            sets TEXT NOT NULL, -- JSON string representing list of {reps, weight_kg}
            date TEXT NOT NULL, -- YYYY-MM-DD
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create calendar_events table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS calendar_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            start_time TEXT NOT NULL, -- YYYY-MM-DD HH:MM
            end_time TEXT NOT NULL, -- YYYY-MM-DD HH:MM
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create plan_exercises table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS plan_exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exercise_name TEXT NOT NULL UNIQUE,
            active INTEGER DEFAULT 1,
            added_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Migrations to handle schema updates on pre-existing databases
    try:
        cursor.execute("ALTER TABLE tasks ADD COLUMN tag TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE tasks ADD COLUMN source TEXT DEFAULT 'manual'")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE tasks ADD COLUMN parent_task_id INTEGER")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE tasks ADD COLUMN completed_at TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE workout_logs ADD COLUMN notes TEXT")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()


def seed_mock_data():
    """Seeds mock data if the tables are currently empty."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if we have calendar events seeded
    cursor.execute("SELECT COUNT(*) FROM calendar_events")
    if cursor.fetchone()[0] == 0:
        today = datetime.now()

        # Seed a single, clearly-labeled example event
        events = [
            (
                "Example Event — connect Google Calendar or add your own",
                today.replace(hour=10, minute=0).strftime("%Y-%m-%d %H:%M"),
                today.replace(hour=11, minute=0).strftime("%Y-%m-%d %H:%M"),
            )
        ]
        cursor.executemany(
            "INSERT INTO calendar_events (title, start_time, end_time) VALUES (?, ?, ?)",
            events,
        )

    # Check if we have habits seeded
    cursor.execute("SELECT COUNT(*) FROM habits")
    if cursor.fetchone()[0] == 0:
        habits = [
            ("Drink 3L Water", "Track daily water consumption", "daily"),
            ("Read 15 Pages", "Read a non-fiction book", "daily"),
            ("Weekly Review", "Plan the upcoming week", "weekly"),
        ]
        cursor.executemany(
            "INSERT INTO habits (name, description, frequency) VALUES (?, ?, ?)", habits
        )

        # Seed some habit logs for the last few days to represent active streaks
        cursor.execute("SELECT id, name FROM habits")
        habits_inserted = cursor.fetchall()

        yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        two_days_ago_str = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")

        for h in habits_inserted:
            if h["name"] == "Drink 3L Water":
                cursor.execute(
                    "INSERT OR IGNORE INTO habit_logs (habit_id, date) VALUES (?, ?)",
                    (h["id"], yesterday_str),
                )
                cursor.execute(
                    "INSERT OR IGNORE INTO habit_logs (habit_id, date) VALUES (?, ?)",
                    (h["id"], two_days_ago_str),
                )
            elif h["name"] == "Read 15 Pages":
                cursor.execute(
                    "INSERT OR IGNORE INTO habit_logs (habit_id, date) VALUES (?, ?)",
                    (h["id"], yesterday_str),
                )

    # Check if we have tasks seeded
    cursor.execute("SELECT COUNT(*) FROM tasks")
    if cursor.fetchone()[0] == 0:
        tasks = [
            (
                "Buy groceries",
                "Milk, Eggs, Spinach, Chicken",
                datetime.now().strftime("%Y-%m-%d"),
                None,
                "open",
                "chore",
                "manual",
            ),
            (
                "Prepare slides for presentation",
                "Q2 Business Update presentation slides",
                (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
                None,
                "open",
                "work",
                "manual",
            ),
            (
                "Water plants",
                "Water balcony and indoor plants",
                (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
                "weekly",
                "completed",
                "chore",
                "plan_generated",
            ),
        ]
        cursor.executemany(
            "INSERT INTO tasks (title, description, due_date, recurrence, status, tag, source) VALUES (?, ?, ?, ?, ?, ?, ?)",
            tasks,
        )

    # Check if we have workout logs seeded
    cursor.execute("SELECT COUNT(*) FROM workout_logs")
    if cursor.fetchone()[0] == 0:
        yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        three_days_ago_str = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
        workouts = [
            (
                "Squats",
                json.dumps(
                    [
                        {"reps": 5, "weight_kg": 80.0},
                        {"reps": 5, "weight_kg": 80.0},
                        {"reps": 5, "weight_kg": 80.0},
                    ]
                ),
                three_days_ago_str,
                "Felt solid",
            ),
            (
                "Bench Press",
                json.dumps(
                    [
                        {"reps": 5, "weight_kg": 60.0},
                        {"reps": 5, "weight_kg": 60.0},
                        {"reps": 5, "weight_kg": 60.0},
                    ]
                ),
                three_days_ago_str,
                "Bar path felt great",
            ),
            (
                "Deadlift",
                json.dumps([{"reps": 5, "weight_kg": 100.0}]),
                three_days_ago_str,
                "Working on back position",
            ),
            (
                "Squats",
                json.dumps(
                    [
                        {"reps": 5, "weight_kg": 82.5},
                        {"reps": 5, "weight_kg": 82.5},
                        {"reps": 5, "weight_kg": 82.5},
                    ]
                ),
                yesterday_str,
                "Hard last set",
            ),
            (
                "Overhead Press",
                json.dumps(
                    [
                        {"reps": 5, "weight_kg": 40.0},
                        {"reps": 5, "weight_kg": 40.0},
                        {"reps": 5, "weight_kg": 40.0},
                    ]
                ),
                yesterday_str,
                "Strict form",
            ),
            (
                "Barbell Row",
                json.dumps(
                    [
                        {"reps": 5, "weight_kg": 50.0},
                        {"reps": 5, "weight_kg": 50.0},
                        {"reps": 5, "weight_kg": 50.0},
                    ]
                ),
                yesterday_str,
                None,
            ),
        ]
        cursor.executemany(
            "INSERT INTO workout_logs (exercise, sets, date, notes) VALUES (?, ?, ?, ?)",
            workouts,
        )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    seed_mock_data()
    print("Database initialized and seeded successfully.")
