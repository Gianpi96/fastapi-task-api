def test_register_success(client):
    response = client.post(
        "/auth/register",
        json={
            "username": "user1",
            "email": "user1@test.com",
            "password": "password123",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "user1"
    assert "id" in data
    assert "hashed_password" not in data  # 🔒 sicurezza


def test_register_duplicate(client):
    user = {
        "username": "dupuser",
        "email": "dup@test.com",
        "password": "password123",
    }

    r1 = client.post("/auth/register", json=user)
    assert r1.status_code == 201  # 👉 assicurati che il primo passi

    response = client.post("/auth/register", json=user)
    assert response.status_code == 400


def test_login_success(client):
    r = client.post(
        "/auth/register",
        json={
            "username": "loginuser",
            "email": "login@test.com",
            "password": "password123",
        },
    )
    assert r.status_code == 201  # 👉 fail immediato se register rompe

    response = client.post(
        "/auth/token",
        data={
            "username": "loginuser",
            "password": "password123",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_credentials(client):
    response = client.post(
        "/auth/token",
        data={"username": "wrong", "password": "wrong"},
    )

    assert response.status_code == 401
