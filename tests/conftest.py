import os
import tempfile

import pytest

import app.db

# Module-level patch during test collection to isolate imports
_temp_dir = tempfile.TemporaryDirectory()
_initial_temp_db = os.path.join(_temp_dir.name, "initial_temp.db")
app.db.DB_PATH = _initial_temp_db
app.db.init_db()


def pytest_sessionfinish(session, exitstatus):
    """Cleanup the initial temporary database directory at session end."""
    try:
        _temp_dir.cleanup()
    except Exception:
        pass


@pytest.fixture(autouse=True, scope="function")
def isolate_db(tmp_path, monkeypatch):
    """Autouse fixture to isolate database calls per test function."""
    temp_db = tmp_path / "test_personal_assistant.db"
    temp_db_str = str(temp_db.resolve())

    # Monkeypatch app.db.DB_PATH to the fresh temp database file
    monkeypatch.setattr(app.db, "DB_PATH", temp_db_str)

    # Initialize the tables and schema for the fresh DB
    app.db.init_db()

    yield

    # Temp file will be cleaned up by pytest's tmp_path fixture,
    # but we can try to explicitly clean it up to release file locks.
    if os.path.exists(temp_db_str):
        try:
            os.remove(temp_db_str)
        except Exception:
            pass
