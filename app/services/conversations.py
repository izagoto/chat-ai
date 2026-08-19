from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.conversation import Conversation, Message


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


def create_conversation(db: Session, user_id: int, title: str = "New chat") -> Conversation:
    conv = Conversation(id=_new_id(), user_id=user_id, title=title[:200])
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def get_owned(db: Session, conversation_id: str, user_id: int) -> Conversation | None:
    return db.scalar(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == conversation_id, Conversation.user_id == user_id)
    )


def list_conversations(db: Session, user_id: int) -> list[tuple[Conversation, int]]:
    count_sq = (
        select(Message.conversation_id, func.count(Message.id).label("n"))
        .group_by(Message.conversation_id)
        .subquery()
    )
    rows = db.execute(
        select(Conversation, func.coalesce(count_sq.c.n, 0))
        .outerjoin(count_sq, Conversation.id == count_sq.c.conversation_id)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
    ).all()
    return [(row[0], int(row[1] or 0)) for row in rows]


def delete_conversation(db: Session, conversation_id: str, user_id: int) -> bool:
    conv = db.scalar(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id)
    )
    if not conv:
        return False
    db.delete(conv)
    db.commit()
    return True


def append_message(
    db: Session,
    conversation: Conversation,
    role: str,
    content: str,
    sources: list[dict] | None = None,
) -> Message:
    payload = None
    if sources:
        payload = json.dumps(sources, ensure_ascii=False)
    msg = Message(conversation_id=conversation.id, role=role, content=content, sources=payload)
    db.add(msg)
    if conversation.title == "New chat" and role == "user":
        conversation.title = content.strip().replace("\n", " ")[:80] or "New chat"
    conversation.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(msg)
    return msg


def replace_user_message(db: Session, conversation: Conversation, message_id: int, content: str) -> Conversation | None:
    """Update a user message and drop every turn after it (ChatGPT-style edit)."""
    target = next((m for m in conversation.messages if m.id == message_id), None)
    if target is None or target.role != "user":
        return None
    text = content.strip()
    if not text:
        return None
    db.execute(
        delete(Message).where(Message.conversation_id == conversation.id, Message.id > message_id)
    )
    target.content = text
    earlier_user = any(m.role == "user" and m.id < message_id for m in conversation.messages)
    if not earlier_user:
        conversation.title = text.replace("\n", " ")[:80] or conversation.title
    conversation.updated_at = datetime.now(timezone.utc)
    db.commit()
    refreshed = get_owned(db, conversation.id, conversation.user_id)
    return refreshed



def history_dicts(conversation: Conversation) -> list[dict[str, str]]:
    max_messages = settings.session_max_turns * 2
    rows = list(conversation.messages)[-max_messages:]
    return [{"role": m.role, "content": m.content} for m in rows]
