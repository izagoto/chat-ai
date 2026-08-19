from fastapi.testclient import TestClient

from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal, init_db
from app.main import app
from app.models.user import User
from app.services.passwords import hash_password

client = TestClient(app)


def _login(email: str | None = None, password: str | None = None) -> tuple[str, int]:
    res = client.post(
        "/v1/auth/login",
        json={
            "email": email or settings.auth_email,
            "password": password or settings.auth_password,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    return body["token"], body["user"]["id"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_conversations_require_login():
    settings.auth_enabled = True
    init_db()
    res = client.get("/v1/conversations")
    assert res.status_code == 401


def test_conversation_crud_and_chat_persist(monkeypatch):
    settings.auth_enabled = True
    init_db()
    token, _user_id = _login()

    created = client.post("/v1/conversations", headers=_auth(token))
    assert created.status_code == 200
    conv = created.json()["conversation"]
    conv_id = conv["id"]
    assert conv["title"] == "New chat"
    assert conv["messages"] == []

    class FakeOllama:
        async def chat(self, messages, temperature=0.5):
            return "pong from alder"

    monkeypatch.setattr("app.api.chat.ollama_client", FakeOllama())

    chat = client.post(
        "/v1/chat",
        headers=_auth(token),
        json={"message": "halo alder", "conversation_id": conv_id, "use_documents": False},
    )
    assert chat.status_code == 200, chat.text
    assert chat.json()["conversation_id"] == conv_id
    assert "pong" in chat.json()["message"]["content"]

    detail = client.get(f"/v1/conversations/{conv_id}", headers=_auth(token))
    assert detail.status_code == 200
    messages = detail.json()["conversation"]["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "halo alder"
    assert "pong" in messages[1]["content"]
    assert detail.json()["conversation"]["title"] == "halo alder"

    listed = client.get("/v1/conversations", headers=_auth(token))
    assert listed.status_code == 200
    row = next(c for c in listed.json()["conversations"] if c["id"] == conv_id)
    assert row["message_count"] == 2
    assert row["title"] == "halo alder"

    deleted = client.delete(f"/v1/conversations/{conv_id}", headers=_auth(token))
    assert deleted.status_code == 200
    missing = client.get(f"/v1/conversations/{conv_id}", headers=_auth(token))
    assert missing.status_code == 404


def test_edit_user_message_truncates_later_turns(monkeypatch):
    settings.auth_enabled = True
    init_db()
    token, _ = _login()
    created = client.post("/v1/conversations", headers=_auth(token))
    conv_id = created.json()["conversation"]["id"]

    replies = iter(["first answer", "second answer", "edited answer"])

    class FakeOllama:
        async def chat(self, messages, temperature=0.5):
            return next(replies)

    monkeypatch.setattr("app.api.chat.ollama_client", FakeOllama())

    first = client.post(
        "/v1/chat",
        headers=_auth(token),
        json={"message": "halo alder", "conversation_id": conv_id, "use_documents": False},
    )
    assert first.status_code == 200, first.text
    second = client.post(
        "/v1/chat",
        headers=_auth(token),
        json={"message": "lanjut", "conversation_id": conv_id, "use_documents": False},
    )
    assert second.status_code == 200, second.text

    detail = client.get(f"/v1/conversations/{conv_id}", headers=_auth(token))
    messages = detail.json()["conversation"]["messages"]
    assert len(messages) == 4
    user_id = messages[0]["id"]

    edited = client.post(
        "/v1/chat",
        headers=_auth(token),
        json={
            "message": "apa perbandingan android dan iphone?",
            "conversation_id": conv_id,
            "use_documents": False,
            "edit_message_id": user_id,
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["message"]["content"] == "edited answer"

    detail = client.get(f"/v1/conversations/{conv_id}", headers=_auth(token))
    messages = detail.json()["conversation"]["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "apa perbandingan android dan iphone?"
    assert messages[1]["content"] == "edited answer"
    assert detail.json()["conversation"]["title"] == "apa perbandingan android dan iphone?"


def test_conversation_not_visible_to_other_user():
    settings.auth_enabled = True
    init_db()
    token_a, _ = _login()
    created = client.post("/v1/conversations", headers=_auth(token_a))
    conv_id = created.json()["conversation"]["id"]

    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == "other@alder.ai"))
        if not existing:
            db.add(
                User(
                    email="other@alder.ai",
                    password_hash=hash_password("Other@2026"),
                    fullname="Other",
                    role="user",
                    is_active=True,
                )
            )
            db.commit()

    token_b, _ = _login("other@alder.ai", "Other@2026")
    peek = client.get(f"/v1/conversations/{conv_id}", headers=_auth(token_b))
    assert peek.status_code == 404


def test_logged_in_documents_use_user_collection(tmp_path, monkeypatch):
    settings.auth_enabled = True
    init_db()
    monkeypatch.setattr("app.services.document_store.settings.documents_path", str(tmp_path / "documents"))
    monkeypatch.setattr("app.services.document_store.settings.rag_use_embeddings", False)

    token, user_id = _login()
    files = {"file": ("note.txt", b"secret-for-this-user", "text/plain")}
    up = client.post("/v1/documents", files=files, headers=_auth(token))
    assert up.status_code == 200, up.text
    assert up.json()["collection_id"] == f"u{user_id}"

    listed = client.get("/v1/documents", headers=_auth(token))
    assert listed.status_code == 200
    assert listed.json()["collection_id"] == f"u{user_id}"
    assert any(d["filename"] == "note.txt" for d in listed.json()["documents"])
