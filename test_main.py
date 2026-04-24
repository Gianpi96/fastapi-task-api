import os
import pytest

os.environ["DATABASE_URL"] = "sqlite:///./test_temp.db"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from database import Base, get_db
from models.user import User  # noqa: F401
from models.tasks import Task  # noqa: F401
from main import app

test_engine = create_engine(
    "sqlite:///./test_temp.db",
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_db():
    yield
    with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    limiter = getattr(app.state, "limiter", None)
    if limiter and hasattr(limiter, "_storage"):
        try:
            limiter._storage.reset()
        except Exception:
            pass
    yield


# ── Helper ────────────────────────────────────────────────
def register(username="mario", email="mario@example.com", password="password123"):
    return client.post(
        "/auth/register",
        json={"username": username, "email": email, "password": password},
    )


def get_token(username="mario", password="password123"):
    r = client.post("/auth/token", data={"username": username, "password": password})
    return r.json().get("access_token")


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── Health ────────────────────────────────────────────────
def test_health():
    assert client.get("/health").json() == {"status": "ok"}


# ── Registrazione ─────────────────────────────────────────
def test_register_ok():
    r = register()
    assert r.status_code == 201
    data = r.json()
    assert data["username"] == "mario"
    assert "hashed_password" not in data


def test_register_duplicate():
    register("luigi", "luigi@example.com")
    r = register("luigi", "luigi@example.com")
    assert r.status_code == 400


def test_register_invalid_email():
    r = client.post(
        "/auth/register",
        json={"username": "test", "email": "noneunemail", "password": "password123"},
    )
    assert r.status_code == 422


def test_register_short_password():
    r = client.post(
        "/auth/register",
        json={"username": "test2", "email": "t@t.com", "password": "123"},
    )
    assert r.status_code == 422


def test_register_short_username():
    r = client.post(
        "/auth/register",
        json={"username": "ab", "email": "ab@ab.com", "password": "password123"},
    )
    assert r.status_code == 422


# ── Login ─────────────────────────────────────────────────
def test_login_ok():
    register("login_user", "login@example.com")
    r = client.post(
        "/auth/token", data={"username": "login_user", "password": "password123"}
    )
    assert r.status_code == 200
    assert "access_token" in r.json()
    assert r.json()["token_type"] == "bearer"


def test_login_wrong_password():
    register("wrongpwd", "wrongpwd@example.com")
    r = client.post(
        "/auth/token", data={"username": "wrongpwd", "password": "sbagliata"}
    )
    assert r.status_code == 401


def test_login_nonexistent_user():
    r = client.post(
        "/auth/token", data={"username": "nonexistent", "password": "qualcosa"}
    )
    assert r.status_code == 401


# ── JWT ───────────────────────────────────────────────────
def test_jwt_has_jti():
    """Ogni token deve avere un jti univoco (necessario per revoca)."""
    import jwt as pyjwt
    from config.settings import settings

    register("jtiuser", "jti@example.com")
    r = client.post(
        "/auth/token", data={"username": "jtiuser", "password": "password123"}
    )
    token = r.json()["access_token"]
    payload = pyjwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    assert "jti" in payload
    assert len(payload["jti"]) > 0


def test_jwt_algorithm_is_hs256():
    """Il token deve usare HS256, non algoritmi deboli."""
    import jwt as pyjwt

    register("algouser", "algo@example.com")
    r = client.post(
        "/auth/token", data={"username": "algouser", "password": "password123"}
    )
    header = pyjwt.get_unverified_header(r.json()["access_token"])
    assert header["alg"] == "HS256"


def test_algo_none_attack():
    """Un token con alg=none non deve essere accettato."""
    import base64, json

    header = (
        base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode())
        .rstrip(b"=")
        .decode()
    )
    payload = (
        base64.urlsafe_b64encode(json.dumps({"sub": "mario"}).encode())
        .rstrip(b"=")
        .decode()
    )

    r = client.get("/tasks", headers={"Authorization": f"Bearer {header}.{payload}."})
    assert r.status_code == 401


# ── Autenticazione task ───────────────────────────────────
def test_tasks_require_auth():
    assert client.get("/tasks").status_code == 401


def test_create_and_get_task():
    register("taskuser", "task@example.com")
    token = get_token("taskuser")

    r = client.post("/tasks", json={"title": "Comprare latte"}, headers=auth(token))
    assert r.status_code == 201
    task_id = r.json()["id"]

    r = client.get(f"/tasks/{task_id}", headers=auth(token))
    assert r.status_code == 200
    assert "latte" in r.json()["title"].lower()


def test_task_isolation_between_users():
    """Un utente non può vedere i task di un altro."""
    register("user_a", "a@example.com")
    token_a = get_token("user_a")

    register("user_b", "b@example.com")
    token_b = get_token("user_b")

    r = client.post("/tasks", json={"title": "Task segreto"}, headers=auth(token_a))
    assert r.status_code == 201
    task_id = r.json()["id"]

    r = client.get(f"/tasks/{task_id}", headers=auth(token_b))
    assert r.status_code == 404


def test_task_title_only_digits_rejected():
    register("numuser", "num@example.com")
    token = get_token("numuser")
    r = client.post("/tasks", json={"title": "123"}, headers=auth(token))
    assert r.status_code == 422


def test_update_task():
    register("updateuser", "update@example.com")
    token = get_token("updateuser")

    r = client.post("/tasks", json={"title": "Da aggiornare"}, headers=auth(token))
    assert r.status_code == 201
    task_id = r.json()["id"]

    r = client.put(
        f"/tasks/{task_id}",
        json={"title": "Aggiornato", "completed": True},
        headers=auth(token),
    )
    assert r.status_code == 200
    assert r.json()["completed"] is True


def test_delete_task():
    register("deluser", "del@example.com")
    token = get_token("deluser")

    r = client.post("/tasks", json={"title": "Da eliminare"}, headers=auth(token))
    assert r.status_code == 201
    task_id = r.json()["id"]

    assert client.delete(f"/tasks/{task_id}", headers=auth(token)).status_code == 200
    assert client.get(f"/tasks/{task_id}", headers=auth(token)).status_code == 404


def test_cannot_delete_other_users_task():
    """Un utente non può eliminare i task di un altro."""
    register("owner", "owner@example.com")
    register("attacker", "attacker@example.com")
    token_owner = get_token("owner")
    token_attacker = get_token("attacker")

    r = client.post(
        "/tasks", json={"title": "Task dell owner"}, headers=auth(token_owner)
    )
    task_id = r.json()["id"]

    r = client.delete(f"/tasks/{task_id}", headers=auth(token_attacker))
    assert r.status_code == 404


# ── Debug endpoint ────────────────────────────────────────
def test_debug_hidden_in_production(monkeypatch):
    monkeypatch.setattr("config.settings.settings.ENV", "production")
    assert client.get("/debug/settings").status_code == 404


def test_debug_visible_in_development(monkeypatch):
    monkeypatch.setattr("config.settings.settings.ENV", "development")
    r = client.get("/debug/settings")
    assert r.status_code == 200
    assert "secret_key_set" in r.json()
