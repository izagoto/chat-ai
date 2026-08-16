"""In-memory session store for short-term chat history."""

from __future__ import annotations

from threading import Lock

from app.core.config import settings


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, list[dict[str, str]]] = {}
        self._lock = Lock()

    def get(self, session_id: str) -> list[dict[str, str]]:
        with self._lock:
            return list(self._sessions.get(session_id, []))

    def append(self, session_id: str, role: str, content: str) -> None:
        with self._lock:
            history = self._sessions.setdefault(session_id, [])
            history.append({"role": role, "content": content})
            max_messages = settings.session_max_turns * 2
            if len(history) > max_messages:
                self._sessions[session_id] = history[-max_messages:]

    def delete(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None


session_store = SessionStore()
