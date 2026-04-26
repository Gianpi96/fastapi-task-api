import os
import pytest

from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Imposta il DB di test PRIMA di qualsiasi import dell'app
os.environ["DATABASE_URL"] = "sqlite:///./test_tasks_temp.db"

from database import Base, get_db  # noqa: E402
from models.user import User  # noqa: F401, E402
from models.tasks import Task  # noqa: F401, E402
from main import app  # noqa: E402

# -----------------------
# DB SETUP
# -----------------------
TEST_DB_URL = "sqlite:///./test_tasks_temp.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


# -----------------------
# FIXTURES
# -----------------------
@pytest.fixture(autouse=True)
def reset_db():
    """Svuota le tabelle prima di ogni test."""
    yield
    with engine.begin() as conn:
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


@pytest.fixture
async def client():
    """Client HTTP asincrono che parla direttamente con l'app ASGI."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
async def auth_headers(client: AsyncClient) -> dict:
    """Registra un utente, fa login e restituisce gli header di autenticazione."""
    await client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123",
        },
    )
    r = await client.post(
        "/auth/token",
        data={
            "username": "testuser",
            "password": "password123",
        },
    )
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# -----------------------
# GET /tasks
# -----------------------
@pytest.mark.anyio
async def test_get_tasks_empty_list(client: AsyncClient, auth_headers: dict):
    """GET /tasks deve restituire 200 e lista vuota se non ci sono task."""
    r = await client.get("/tasks", headers=auth_headers)

    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.anyio
async def test_get_tasks_returns_only_own(client: AsyncClient, auth_headers: dict):
    """GET /tasks deve restituire solo i task dell'utente autenticato."""
    await client.post("/tasks", json={"title": "Task mio"}, headers=auth_headers)

    r = await client.get("/tasks", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["title"] == "Task mio"


@pytest.mark.anyio
async def test_get_tasks_requires_auth(client: AsyncClient):
    """GET /tasks senza token deve restituire 401."""
    r = await client.get("/tasks")
    assert r.status_code == 401


# -----------------------
# POST /tasks
# -----------------------
@pytest.mark.anyio
async def test_create_task_201(client: AsyncClient, auth_headers: dict):
    """POST /tasks deve restituire 201 e il task creato."""
    payload = {"title": "Comprare latte", "description": "Intero", "completed": False}

    r = await client.post("/tasks", json=payload, headers=auth_headers)

    assert r.status_code == 201
    data = r.json()
    assert data["title"] == "Comprare latte"
    assert data["description"] == "Intero"
    assert data["completed"] is False
    assert "id" in data
    assert "owner_id" in data


@pytest.mark.anyio
async def test_create_task_title_too_short(client: AsyncClient, auth_headers: dict):
    """POST /tasks con titolo < 3 caratteri deve restituire 422."""
    r = await client.post("/tasks", json={"title": "ab"}, headers=auth_headers)
    assert r.status_code == 422


@pytest.mark.anyio
async def test_create_task_title_only_digits(client: AsyncClient, auth_headers: dict):
    """POST /tasks con titolo composto solo da numeri deve restituire 422."""
    r = await client.post("/tasks", json={"title": "123"}, headers=auth_headers)
    assert r.status_code == 422


@pytest.mark.anyio
async def test_create_task_requires_auth(client: AsyncClient):
    """POST /tasks senza token deve restituire 401."""
    r = await client.post("/tasks", json={"title": "Task senza auth"})
    assert r.status_code == 401


# -----------------------
# GET /tasks/{id}
# -----------------------
@pytest.mark.anyio
async def test_get_task_by_id_200(client: AsyncClient, auth_headers: dict):
    """GET /tasks/{id} deve restituire 200 e il task corretto."""
    created = await client.post(
        "/tasks", json={"title": "Task specifico"}, headers=auth_headers
    )
    task_id = created.json()["id"]

    r = await client.get(f"/tasks/{task_id}", headers=auth_headers)

    assert r.status_code == 200
    assert r.json()["id"] == task_id
    assert r.json()["title"] == "Task specifico"


@pytest.mark.anyio
async def test_get_task_by_id_404(client: AsyncClient, auth_headers: dict):
    """GET /tasks/{id} con id inesistente deve restituire 404."""
    r = await client.get("/tasks/99999", headers=auth_headers)
    assert r.status_code == 404


@pytest.mark.anyio
async def test_get_task_other_user_404(client: AsyncClient, auth_headers: dict):
    """GET /tasks/{id} di un altro utente deve restituire 404 (isolamento)."""
    # Crea task con utente A
    created = await client.post(
        "/tasks", json={"title": "Task di A"}, headers=auth_headers
    )
    task_id = created.json()["id"]

    # Registra e logga utente B
    await client.post(
        "/auth/register",
        json={
            "username": "userb",
            "email": "b@example.com",
            "password": "password123",
        },
    )
    r = await client.post(
        "/auth/token", data={"username": "userb", "password": "password123"}
    )
    headers_b = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # B non deve vedere il task di A
    r = await client.get(f"/tasks/{task_id}", headers=headers_b)
    assert r.status_code == 404


# -----------------------
# DELETE /tasks/{id}
# -----------------------
@pytest.mark.anyio
async def test_delete_task_200(client: AsyncClient, auth_headers: dict):
    """DELETE /tasks/{id} deve restituire 200 e il task non deve più esistere."""
    created = await client.post(
        "/tasks", json={"title": "Task da eliminare"}, headers=auth_headers
    )
    task_id = created.json()["id"]

    r = await client.delete(f"/tasks/{task_id}", headers=auth_headers)
    assert r.status_code == 200

    # Verifica che il task non esista più
    r = await client.get(f"/tasks/{task_id}", headers=auth_headers)
    assert r.status_code == 404


@pytest.mark.anyio
async def test_delete_task_404(client: AsyncClient, auth_headers: dict):
    """DELETE /tasks/{id} con id inesistente deve restituire 404."""
    r = await client.delete("/tasks/99999", headers=auth_headers)
    assert r.status_code == 404


@pytest.mark.anyio
async def test_delete_task_other_user_404(client: AsyncClient, auth_headers: dict):
    """DELETE /tasks/{id} di un altro utente deve restituire 404."""
    created = await client.post(
        "/tasks", json={"title": "Task protetto"}, headers=auth_headers
    )
    task_id = created.json()["id"]

    await client.post(
        "/auth/register",
        json={
            "username": "attacker",
            "email": "attacker@example.com",
            "password": "password123",
        },
    )
    r = await client.post(
        "/auth/token", data={"username": "attacker", "password": "password123"}
    )
    headers_attacker = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = await client.delete(f"/tasks/{task_id}", headers=headers_attacker)
    assert r.status_code == 404

    # Il task originale deve esistere ancora
    r = await client.get(f"/tasks/{task_id}", headers=auth_headers)
    assert r.status_code == 200
