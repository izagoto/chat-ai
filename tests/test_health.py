from fastapi.testclient import TestClient

from app.main import app
from app.services.ollama import model_is_installed


client = TestClient(app)


def test_health_endpoint_shape():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "ollama" in data
    assert "model" in data
    assert "request_id" in data
    assert resp.headers.get("X-Request-ID")


def test_model_is_installed_matches_tags():
    installed = ["llama3.2:3b", "nomic-embed-text:latest"]
    assert model_is_installed("llama3.2:3b", installed)
    assert model_is_installed("nomic-embed-text", installed)
    assert not model_is_installed("llama3.2:8b", installed)
    assert not model_is_installed("", installed)
