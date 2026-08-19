from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.session import init_db
from app.main import app
from app.services.prompts import ASSISTANT_SYSTEM

client = TestClient(app)


def _login() -> dict[str, str]:
    settings.auth_enabled = True
    init_db()
    res = client.post(
        "/v1/auth/login",
        json={"email": settings.auth_email, "password": settings.auth_password},
    )
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['token']}"}


def test_prompt_requires_login():
    settings.auth_enabled = True
    init_db()
    res = client.get("/v1/prompt")
    assert res.status_code == 401


def test_prompt_get_default_and_update(monkeypatch):
    headers = _login()
    got = client.get("/v1/prompt", headers=headers)
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["prompt"] == ASSISTANT_SYSTEM
    assert body["is_custom"] is False

    saved = client.put("/v1/prompt", headers=headers, json={"prompt": "You are a terse analyst. Answer in one sentence."})
    assert saved.status_code == 200, saved.text
    assert saved.json()["is_custom"] is True
    assert "terse analyst" in saved.json()["prompt"]

    captured = {}

    class FakeOllama:
        async def chat(self, messages, temperature=0.5):
            captured["system"] = messages[0]["content"]
            return "ok"

    monkeypatch.setattr("app.api.chat.ollama_client", FakeOllama())
    chat = client.post(
        "/v1/chat",
        headers=headers,
        json={"message": "hai", "use_documents": False},
    )
    assert chat.status_code == 200, chat.text
    assert "terse analyst" in captured["system"]

    reset = client.put("/v1/prompt", headers=headers, json={"prompt": ""})
    assert reset.status_code == 200
    assert reset.json()["is_custom"] is False
    assert reset.json()["prompt"] == ASSISTANT_SYSTEM
