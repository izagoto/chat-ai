from fastapi import APIRouter, Request

from app.core.logging import get_request_id
from app.models.schemas import HealthResponse
from app.services.ollama import ollama_client
from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    info = await ollama_client.health()
    ollama_status = info["status"]
    overall = "ok" if ollama_status == "up" and not info.get("detail") else "degraded"
    return HealthResponse(
        status=overall,
        ollama=ollama_status,
        model=settings.ollama_model,
        request_id=get_request_id(request),
        detail=info.get("detail"),
    )
