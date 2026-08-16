from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.logging import get_request_id
from app.core.security import require_api_key
from app.models.schemas import AskRequest, AskResponse, SafetyInfo, SourceItem
from app.services.ollama import OllamaError
from app.services.rag import rag_service
from app.services.safety import safety_service

router = APIRouter(tags=["ask"])


@router.post("/ask", response_model=AskResponse)
async def ask(body: AskRequest, request: Request, _: None = Depends(require_api_key)) -> AskResponse:
    request_id = get_request_id(request)

    inbound = safety_service.check_input(body.question, body.safety_mode)
    if inbound.blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "request_id": request_id,
                "error": "prompt_blocked",
                "reason": "Possible prompt injection pattern detected",
            },
        )

    try:
        answer, sources = await rag_service.answer(body.question, top_k=body.top_k)
    except OllamaError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "request_id": request_id,
                "error": "ollama_unavailable",
                "detail": str(exc),
            },
        ) from exc

    outbound = safety_service.sanitize_output(answer)
    return AskResponse(
        request_id=request_id,
        answer=outbound.text,
        sources=[SourceItem(**s) for s in sources],
        safety=SafetyInfo(
            input_flagged=inbound.flagged,
            output_redacted=outbound.redacted,
            reasons=[*inbound.reasons, *outbound.reasons],
        ),
    )
