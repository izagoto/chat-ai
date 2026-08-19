import time

import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def disable_auth_for_tests():
    previous = settings.auth_enabled
    settings.auth_enabled = False
    yield
    settings.auth_enabled = previous


def wait_until_ready(client, document_id, *, headers=None, timeout=8.0):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        listed = client.get("/v1/documents", headers=headers)
        docs = listed.json().get("documents") or []
        last = next((d for d in docs if d["document_id"] == document_id), None)
        if last and last.get("status") == "ready":
            return last
        if last and last.get("status") == "failed":
            raise AssertionError(last.get("error") or "ingest failed")
        time.sleep(0.05)
    raise AssertionError(f"timed out waiting for {document_id} to be ready: {last}")
