from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.logging import get_request_id
from app.core.security import require_session
from app.db.session import get_db
from app.models.schemas import LoginRequest, LoginResponse, UserOut
from app.services.auth import authenticate, issue_token

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)) -> LoginResponse:
    user = authenticate(db, str(body.email), body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "request_id": get_request_id(request),
                "error": "invalid_credentials",
                "detail": "Email atau password salah.",
            },
        )
    token = issue_token(user.email)
    return LoginResponse(
        request_id=get_request_id(request),
        token=token,
        user=UserOut(id=user.id, email=user.email, fullname=user.fullname, role=user.role),
    )


@router.get("/auth/me")
async def me(request: Request, _: None = Depends(require_session)) -> dict:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "request_id": get_request_id(request),
                "error": "unauthorized",
                "detail": "Login required",
            },
        )
    return {
        "request_id": get_request_id(request),
        "user": {
            "id": user.id,
            "email": user.email,
            "fullname": user.fullname,
            "role": user.role,
        },
    }
