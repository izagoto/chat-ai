import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.logging import get_request_id
from app.core.owners import request_user
from app.core.security import require_api_key
from app.db.session import get_db
from app.models.schemas import (
    ConversationDetail,
    ConversationListResponse,
    ConversationOut,
    ConversationResponse,
    MessageOut,
    SourceItem,
)
from app.services import conversations as conv_svc

router = APIRouter(tags=["conversations"])


def _require_user(request: Request):
    user = request_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "request_id": get_request_id(request),
                "error": "unauthorized",
                "detail": "Login required",
            },
        )
    return user


def _iso(dt) -> str:
    return dt.isoformat()


def _parse_sources(raw: str | None) -> list[SourceItem]:
    if not raw:
        return []
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(items, list):
        return []
    out: list[SourceItem] = []
    for item in items:
        if not isinstance(item, dict) or not item.get("file"):
            continue
        out.append(SourceItem(**item))
    return out


def _to_out(conv, message_count: int | None = None) -> ConversationOut:
    count = message_count if message_count is not None else len(conv.messages or [])
    return ConversationOut(
        id=conv.id,
        title=conv.title,
        created_at=_iso(conv.created_at),
        updated_at=_iso(conv.updated_at),
        message_count=count,
    )


def _to_detail(conv) -> ConversationDetail:
    base = _to_out(conv)
    return ConversationDetail(
        **base.model_dump(),
        messages=[
            MessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                created_at=_iso(m.created_at),
                sources=_parse_sources(m.sources),
            )
            for m in (conv.messages or [])
        ],
    )


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    request: Request,
    _: None = Depends(require_api_key),
    db: Session = Depends(get_db),
) -> ConversationResponse:
    user = _require_user(request)
    conv = conv_svc.create_conversation(db, user.id)
    return ConversationResponse(request_id=get_request_id(request), conversation=_to_detail(conv))


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    request: Request,
    _: None = Depends(require_api_key),
    db: Session = Depends(get_db),
) -> ConversationListResponse:
    user = _require_user(request)
    items = conv_svc.list_conversations(db, user.id)
    return ConversationListResponse(
        request_id=get_request_id(request),
        conversations=[_to_out(c, message_count=n) for c, n in items],
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    request: Request,
    _: None = Depends(require_api_key),
    db: Session = Depends(get_db),
) -> ConversationResponse:
    user = _require_user(request)
    conv = conv_svc.get_owned(db, conversation_id, user.id)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "request_id": get_request_id(request),
                "error": "not_found",
                "detail": "Conversation not found",
            },
        )
    return ConversationResponse(request_id=get_request_id(request), conversation=_to_detail(conv))


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    request: Request,
    _: None = Depends(require_api_key),
    db: Session = Depends(get_db),
) -> dict:
    user = _require_user(request)
    ok = conv_svc.delete_conversation(db, conversation_id, user.id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "request_id": get_request_id(request),
                "error": "not_found",
                "detail": "Conversation not found",
            },
        )
    return {"request_id": get_request_id(request), "deleted": True, "conversation_id": conversation_id}
