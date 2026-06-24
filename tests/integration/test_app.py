from fastapi.testclient import TestClient

from app.db import get_db_connection
from app.main import app


def test_get_habits_items_endpoint():
    # Seed a habit first in the isolated test DB
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO habits (name, frequency, description, created_at) VALUES ('Water Plants Test', 'daily', 'Water plants daily', '2026-06-20')"
    )
    conn.commit()
    conn.close()

    client = TestClient(app)
    response = client.get("/habits/items")
    assert response.status_code == 200
    assert "Error:" not in response.text
    assert "Water Plants Test" in response.text
    assert "habit-heatmap" in response.text
