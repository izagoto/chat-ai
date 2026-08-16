import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.core.logging import get_request_id
from app.core.security import require_api_key
from app.models.schemas import ChatMessage, ChatRequest, ChatResponse, SafetyInfo
from app.services.ollama import OllamaError, ollama_client
from app.services.safety import safety_service
from app.services.session import session_store

router = APIRouter(tags=["chat"])

SYSTEM_PROMPT = (
    "You are Local Secure AI, a helpful on-premise assistant. "
    "Be concise, accurate, and refuse requests for illegal hacking activity. "
    "Prefer answering in the user's language."
)


def _blocked_response(request_id: str, reason: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "request_id": request_id,
            "error": "prompt_blocked",
            "reason": reason,
        },
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, request: Request, _: None = Depends(require_api_key)) -> ChatResponse:
    request_id = get_request_id(request)
    session_id = body.session_id or "default"

    inbound = safety_service.check_input(body.message, body.safety_mode)
    if inbound.blocked:
        raise _blocked_response(request_id, "Possible prompt injection pattern detected")

    history = session_store.get(session_id)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history, {"role": "user", "content": body.message}]

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
    session_store.append(session_id, "user", body.message)
    session_store.append(session_id, "assistant", outbound.text)

    return ChatResponse(
        request_id=request_id,
        session_id=session_id,
        message=ChatMessage(role="assistant", content=outbound.text),
        safety=SafetyInfo(
            input_flagged=inbound.flagged,
            output_redacted=outbound.redacted,
            reasons=[*inbound.reasons, *outbound.reasons],
        ),
        usage={"prompt_tokens": None, "completion_tokens": None},
    )


@router.post("/chat/stream")
async def chat_stream(body: ChatRequest, request: Request, _: None = Depends(require_api_key)) -> StreamingResponse:
    request_id = get_request_id(request)
    session_id = body.session_id or "default"

    inbound = safety_service.check_input(body.message, body.safety_mode)
    if inbound.blocked:
        raise _blocked_response(request_id, "Possible prompt injection pattern detected")

    history = session_store.get(session_id)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history, {"role": "user", "content": body.message}]

    async def event_generator():
        collected: list[str] = []
        try:
            async for delta in ollama_client.chat_stream(messages, temperature=body.temperature):
                collected.append(delta)
                yield f"data: {json.dumps({'type': 'delta', 'content': delta, 'request_id': request_id})}\n\n"

            full = "".join(collected)
            outbound = safety_service.sanitize_output(full)
            session_store.append(session_id, "user", body.message)
            session_store.append(session_id, "assistant", outbound.text)
            yield f"data: {json.dumps({'type': 'done', 'request_id': request_id, 'output_redacted': outbound.redacted})}\n\n"
        except OllamaError as exc:
            yield f"data: {json.dumps({'type': 'error', 'detail': str(exc), 'request_id': request_id})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
