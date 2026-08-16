from fastapi import Header, HTTPException, Request, status

from app.core.config import settings
from app.core.logging import get_request_id


async def require_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """Optional local API key gate. Disabled when LOCAL_API_KEY is empty."""
    if not settings.local_api_key:
        return
    if x_api_key != settings.local_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "request_id": get_request_id(request),
                "error": "unauthorized",
                "detail": "Invalid or missing X-API-Key",
            },
        )
