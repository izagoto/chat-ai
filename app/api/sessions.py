from fastapi import APIRouter, Depends, Request

from app.core.logging import get_request_id
from app.core.security import require_api_key
from app.models.schemas import SessionDeleteResponse
from app.services.session import session_store

router = APIRouter(tags=["sessions"])


@router.delete("/sessions/{session_id}", response_model=SessionDeleteResponse)
async def delete_session(
    session_id: str,
    request: Request,
    _: None = Depends(require_api_key),
) -> SessionDeleteResponse:
    deleted = session_store.delete(session_id)
    return SessionDeleteResponse(
        deleted=deleted,
        session_id=session_id,
        request_id=get_request_id(request),
    )
