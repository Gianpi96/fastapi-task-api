# test_task.py — VERSIONE CORRETTA
# Niente import di engine/sessionmaker/fixture: li prende da conftest.py


def test_get_tasks_empty(client, auth_headers):
    r = client.get("/tasks", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_create_task(client, auth_headers):
    r = client.post("/tasks", json={"title": "Comprare latte"}, headers=auth_headers)
    assert r.status_code == 201
    data = r.json()
    assert data["title"] == "Comprare latte"
    assert "id" in data


def test_get_tasks_requires_auth(client):
    r = client.get("/tasks")
    assert r.status_code == 401


def test_get_task_by_id(client, auth_headers):
    created = client.post("/tasks", json={"title": "Task 1"}, headers=auth_headers)
    task_id = created.json()["id"]
    r = client.get(f"/tasks/{task_id}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["id"] == task_id


def test_delete_task(client, auth_headers):
    created = client.post(
        "/tasks", json={"title": "Da eliminare"}, headers=auth_headers
    )
    task_id = created.json()["id"]
    r = client.delete(f"/tasks/{task_id}", headers=auth_headers)
    assert r.status_code == 200
    r = client.get(f"/tasks/{task_id}", headers=auth_headers)
    assert r.status_code == 404
