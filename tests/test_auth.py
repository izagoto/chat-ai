from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.session import init_db
from app.main import app

client = TestClient(app)


def test_login_success():
    settings.auth_enabled = True
    init_db()
    res = client.post(
        "/v1/auth/login",
        json={"email": settings.auth_email, "password": settings.auth_password},
    )
    assert res.status_code == 200
    assert res.json()["token"]
    assert res.json()["user"]["email"] == settings.auth_email.lower()


def test_login_rejects_bad_password():
    settings.auth_enabled = True
    init_db()
    res = client.post(
        "/v1/auth/login",
        json={"email": settings.auth_email, "password": "wrong"},
    )
    assert res.status_code == 401


def test_protected_route_requires_login():
    settings.auth_enabled = True
    init_db()
    res = client.get("/v1/documents")
    assert res.status_code == 401

    login = client.post(
        "/v1/auth/login",
        json={"email": settings.auth_email, "password": settings.auth_password},
    )
    token = login.json()["token"]
    ok = client.get("/v1/documents", headers={"Authorization": f"Bearer {token}"})
    assert ok.status_code == 200
