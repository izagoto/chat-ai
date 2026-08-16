from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_endpoint_shape():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "ollama" in data
    assert "request_id" in data
    assert resp.headers.get("X-Request-ID")
