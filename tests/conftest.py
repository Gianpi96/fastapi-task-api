import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from database import Base, get_db

# ✅ DB di test SEPARATO
TEST_DATABASE_URL = "sqlite:///./test.db"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

TestingSessionLocal = sessionmaker(
    bind=test_engine,
    autoflush=False,
    autocommit=False,
)


# -----------------------
# FIXTURE DB
# -----------------------
@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=test_engine)


# -----------------------
# OVERRIDE DEPENDENCY
# -----------------------
@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


# -----------------------
# AUTH FIXTURE
# -----------------------
@pytest.fixture
def auth_headers(client):
    client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "email": "test@test.com",
            "password": "password123",
        },
    )

    response = client.post(
        "/auth/token",
        data={
            "username": "testuser",
            "password": "password123",
        },
    )

    token = response.json()["access_token"]

    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def disable_rate_limit():
    if hasattr(app.state, "limiter"):
        app.state.limiter.enabled = False
    yield
