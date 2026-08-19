import json
import re

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.logging import get_request_id
from app.core.owners import collection_id_for_request, request_user
from app.core.security import require_api_key
from app.db.session import SessionLocal, get_db
from app.models.schemas import ChatMessage, ChatRequest, ChatResponse, SafetyInfo, SourceItem
from app.services import conversations as conv_svc
from app.services.citations import sources_from_hits
from app.services.document_store import document_store
from app.services.ollama import OllamaError, ollama_client
from app.services.prompts import ASSISTANT_SYSTEM, with_rag_notes
from app.services.user_prompts import load_system_prompt
from app.services.safety import safety_service
from app.services.session import session_store

router = APIRouter(tags=["chat"])

_CASUAL = re.compile(
    r"^(hi+|hello|hey|hai|halo|hallo|pagi|siang|sore|malam|"
    r"ok+|oke|okay|ya+|yup|thanks|thank you|terima kasih|makasih|"
    r"test|tes|ping|chat|chating|ngobrol)[\s!.?]*$",
    re.I,
)


_FILE_HINT = re.compile(
    r"\b(dokumen|document|file|pdf|unggah|upload|gambar|image|excel|csv|catatan|notes?|"
    r"ringkas|summarize|excerpt|url|tautan|link|website|halaman)\b",
    re.I,
)


def _wants_document_context(message: str) -> bool:
    text = message.strip()
    if not text or _CASUAL.match(text):
        return False
    if _FILE_HINT.search(text):
        return True
    words = text.split()
    if len(words) <= 2 and len(text) < 12 and not re.search(r"\d", text):
        return False
    return True


async def _prepare_messages(
    body: ChatRequest,
    collection_id: str,
    history: list[dict[str, str]],
    system_prompt: str | None = None,
) -> tuple[list[dict[str, str]], list[SourceItem]]:
    sources: list[SourceItem] = []
    system = (system_prompt or "").strip() or ASSISTANT_SYSTEM
    if body.use_documents and _wants_document_context(body.message):
        hits = await document_store.retrieve(collection_id, body.message, top_k=3)
        if hits:
            sources = sources_from_hits(hits)
            system = with_rag_notes(system)
            blocks = []
            for chunk, score in hits:
                loc = chunk.location or {}
                blocks.append(
                    f"- {chunk.source_file} (score={score:.2f}, loc={loc}): {chunk.text[:400]}"
                )
            system += (
                "\n\nOptional notes from the user's files. "
                "Ignore them unless they clearly answer the question:\n" + "\n".join(blocks)
            )

    messages = [
        {"role": "system", "content": system},
        *history,
        {"role": "user", "content": body.message.strip()},
    ]
    return messages, sources


def _persist_turn(
    conversation_id: str,
    user_id: int,
    user_text: str,
    assistant_text: str,
    sources: list[SourceItem] | None = None,
    persist_user: bool = True,
) -> None:
    payload = [s.model_dump() for s in sources] if sources else None
    with SessionLocal() as persist:
        conv = conv_svc.get_owned(persist, conversation_id, user_id)
        if not conv:
            return
        if persist_user:
            conv_svc.append_message(persist, conv, "user", user_text)
        conv_svc.append_message(persist, conv, "assistant", assistant_text, sources=payload)


def _blocked_response(request_id: str, reason: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "request_id": request_id,
            "error": "prompt_blocked",
            "reason": reason,
        },
    )


def _load_conversation(db: Session, request: Request, body: ChatRequest):
    user = request_user(request)
    if body.edit_message_id:
        if not user or not body.conversation_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "request_id": get_request_id(request),
                    "error": "invalid_edit",
                    "detail": "Editing requires an existing conversation",
                },
            )
        conv = conv_svc.get_owned(db, body.conversation_id, user.id)
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "request_id": get_request_id(request),
                    "error": "not_found",
                    "detail": "Conversation not found",
                },
            )
        return conv
    if not user:
        return None
    if body.conversation_id:
        conv = conv_svc.get_owned(db, body.conversation_id, user.id)
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "request_id": get_request_id(request),
                    "error": "not_found",
                    "detail": "Conversation not found",
                },
            )
        return conv
    return conv_svc.create_conversation(db, user.id)


def _apply_message_edit(db: Session, conversation, body: ChatRequest, request: Request):
    if not body.edit_message_id:
        return conversation
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "request_id": get_request_id(request),
                "error": "invalid_edit",
                "detail": "Editing requires an existing conversation",
            },
        )
    updated = conv_svc.replace_user_message(db, conversation, body.edit_message_id, body.message)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "request_id": get_request_id(request),
                "error": "not_found",
                "detail": "Message not found",
            },
        )
    return updated


def _history_for_chat(conversation, session_id: str, body: ChatRequest) -> list[dict[str, str]]:
    history = conv_svc.history_dicts(conversation) if conversation else session_store.get(session_id)
    if body.edit_message_id and history and history[-1]["role"] == "user":
        return history[:-1]
    return history


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    request: Request,
    _: None = Depends(require_api_key),
    db: Session = Depends(get_db),
) -> ChatResponse:
    request_id = get_request_id(request)
    session_id = body.session_id or "default"
    collection_id = collection_id_for_request(request, body.collection_id)

    inbound = safety_service.check_input(body.message, body.safety_mode)
    if inbound.blocked:
        raise _blocked_response(request_id, "Possible prompt injection pattern detected")

    conversation = _load_conversation(db, request, body)
    conversation = _apply_message_edit(db, conversation, body, request)

    history = _history_for_chat(conversation, session_id, body)
    user = request_user(request)
    system_prompt = load_system_prompt(db, user.id if user else None)
    messages, sources = await _prepare_messages(body, collection_id, history, system_prompt)

    try:
        content = await ollama_client.chat(messages, temperature=body.temperature)
    except OllamaError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT if not exc.unavailable else status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "request_id": request_id,
                "error": "ollama_unavailable",
                "detail": str(exc),
            },
        ) from exc

    outbound = safety_service.sanitize_output(content)
    if conversation:
        _persist_turn(
            conversation.id,
            conversation.user_id,
            body.message,
            outbound.text,
            sources,
            persist_user=body.edit_message_id is None,
        )
    else:
        session_store.append(session_id, "user", body.message)
        session_store.append(session_id, "assistant", outbound.text)

    return ChatResponse(
        request_id=request_id,
        session_id=session_id,
        conversation_id=conversation.id if conversation else None,
        message=ChatMessage(role="assistant", content=outbound.text),
        sources=sources,
        safety=SafetyInfo(
            input_flagged=inbound.flagged,
            output_redacted=outbound.redacted,
            reasons=[*inbound.reasons, *outbound.reasons],
        ),
        usage={"prompt_tokens": None, "completion_tokens": None},
    )


@router.post("/chat/stream")
async def chat_stream(
    body: ChatRequest,
    request: Request,
    _: None = Depends(require_api_key),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    request_id = get_request_id(request)
    session_id = body.session_id or "default"
    collection_id = collection_id_for_request(request, body.collection_id)

    inbound = safety_service.check_input(body.message, body.safety_mode)
    if inbound.blocked:
        raise _blocked_response(request_id, "Possible prompt injection pattern detected")

    conversation = _load_conversation(db, request, body)
    conversation = _apply_message_edit(db, conversation, body, request)

    history = _history_for_chat(conversation, session_id, body)
    user = request_user(request)
    system_prompt = load_system_prompt(db, user.id if user else None)
    messages, sources = await _prepare_messages(body, collection_id, history, system_prompt)
    conversation_id = conversation.id if conversation else None
    conversation_user_id = conversation.user_id if conversation else None
    persist_user = body.edit_message_id is None
    sources_payload = [s.model_dump() for s in sources]

    async def event_generator():
        collected: list[str] = []
        try:
            if sources_payload:
                yield f"data: {json.dumps({'type': 'sources', 'sources': sources_payload, 'request_id': request_id})}\n\n"
            async for delta in ollama_client.chat_stream(messages, temperature=body.temperature):
                collected.append(delta)
                yield f"data: {json.dumps({'type': 'delta', 'content': delta, 'request_id': request_id})}\n\n"

            full = "".join(collected)
            outbound = safety_service.sanitize_output(full)
            if conversation_id and conversation_user_id is not None:
                _persist_turn(
                    conversation_id,
                    conversation_user_id,
                    body.message,
                    outbound.text,
                    sources,
                    persist_user=persist_user,
                )
            else:
                session_store.append(session_id, "user", body.message)
                session_store.append(session_id, "assistant", outbound.text)
            yield f"data: {json.dumps({'type': 'done', 'request_id': request_id, 'conversation_id': conversation_id, 'output_redacted': outbound.redacted, 'sources': sources_payload})}\n\n"
        except OllamaError as exc:
            yield f"data: {json.dumps({'type': 'error', 'detail': str(exc), 'request_id': request_id})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
