from fastapi import Request

from app.core.config import settings
from app.services.auth import AuthUser


def request_user(request: Request) -> AuthUser | None:
    return getattr(request.state, "user", None)


def collection_id_for_request(request: Request, requested: str | None = None) -> str:
    """Logged-in users get an isolated collection; ignore client-supplied ids."""
    user = request_user(request)
    if user:
        return f"u{user.id}"
    coll = (requested or settings.default_collection).strip()
    return coll or settings.default_collection
