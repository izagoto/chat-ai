from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_request_id
from app.db.session import get_db
from app.services.auth import parse_token


def _unauthorized(request: Request, detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "request_id": get_request_id(request),
            "error": "unauthorized",
            "detail": detail,
        },
    )


async def require_api_key(
    request: Request,
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None),
) -> None:
    """Login session (Bearer) and/or optional X-API-Key."""
    if settings.auth_enabled:
        token = None
        if authorization and authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1].strip()
        user = parse_token(token or "", db)
        if not user:
            raise _unauthorized(request, "Login required")
        request.state.user = user

    if settings.local_api_key and x_api_key != settings.local_api_key:
        raise _unauthorized(request, "Invalid or missing X-API-Key")


async def require_session(request: Request, _: None = Depends(require_api_key)) -> None:
    return None
