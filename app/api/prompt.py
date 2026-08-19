from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.logging import get_request_id
from app.core.owners import request_user
from app.core.security import require_api_key
from app.db.session import get_db
from app.models.schemas import PromptResponse, PromptUpdateRequest
from app.services.prompts import ASSISTANT_SYSTEM
from app.services.user_prompts import load_system_prompt, save_system_prompt

router = APIRouter(tags=["prompt"])


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


@router.get("/prompt", response_model=PromptResponse)
async def get_prompt(
    request: Request,
    _: None = Depends(require_api_key),
    db: Session = Depends(get_db),
) -> PromptResponse:
    user = _require_user(request)
    prompt = load_system_prompt(db, user.id)
    return PromptResponse(
        request_id=get_request_id(request),
        prompt=prompt,
        default_prompt=ASSISTANT_SYSTEM,
        is_custom=prompt != ASSISTANT_SYSTEM,
    )


@router.put("/prompt", response_model=PromptResponse)
async def update_prompt(
    body: PromptUpdateRequest,
    request: Request,
    _: None = Depends(require_api_key),
    db: Session = Depends(get_db),
) -> PromptResponse:
    user = _require_user(request)
    try:
        prompt, is_custom = save_system_prompt(db, user.id, body.prompt)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "request_id": get_request_id(request),
                "error": "invalid_prompt",
                "detail": str(exc),
            },
        ) from exc
    return PromptResponse(
        request_id=get_request_id(request),
        prompt=prompt,
        default_prompt=ASSISTANT_SYSTEM,
        is_custom=is_custom,
    )
