from sqlalchemy.orm import Session

from app.models.user import User
from app.services.prompts import MAX_SYSTEM_PROMPT_CHARS, effective_system_prompt, normalize_system_prompt


def load_system_prompt(db: Session, user_id: int | None) -> str:
    if not user_id:
        return effective_system_prompt(None)
    user = db.get(User, user_id)
    return effective_system_prompt(user.system_prompt if user else None)


def save_system_prompt(db: Session, user_id: int, prompt: str | None) -> tuple[str, bool]:
    user = db.get(User, user_id)
    if not user:
        raise ValueError("user not found")
    text = (prompt or "").strip()
    if len(text) > MAX_SYSTEM_PROMPT_CHARS:
        raise ValueError(f"Prompt too long (max {MAX_SYSTEM_PROMPT_CHARS} characters)")
    stored = normalize_system_prompt(text)
    user.system_prompt = stored
    db.commit()
    db.refresh(user)
    effective = effective_system_prompt(stored)
    return effective, stored is not None
