from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.config import settings
from app.core.logging import get_request_id
from app.core.security import require_api_key
from app.models.schemas import ModelsResponse
from app.services.ollama import OllamaError, ollama_client

router = APIRouter(tags=["models"])


@router.get("/models", response_model=ModelsResponse)
async def list_models(request: Request, _: None = Depends(require_api_key)) -> ModelsResponse:
    request_id = get_request_id(request)
    try:
        models = await ollama_client.list_models()
    except OllamaError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "request_id": request_id,
                "error": "ollama_unavailable",
                "detail": str(exc),
            },
        ) from exc

    return ModelsResponse(models=models, active=settings.ollama_model, request_id=request_id)
