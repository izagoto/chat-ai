from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables and seed the default user if missing."""
    if settings.database_url.startswith("sqlite:///"):
        db_path = settings.database_url.replace("sqlite:///", "", 1)
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    # Import models so metadata is populated.
    from app.models.conversation import Conversation, Message  # noqa: F401
    from app.models.user import User  # noqa: F401
    from app.services.passwords import hash_password

    Base.metadata.create_all(bind=engine)
    _ensure_message_sources_column()
    _ensure_user_system_prompt_column()

    with SessionLocal() as db:
        _migrate_legacy_seed_user(db, hash_password)
        email = settings.auth_email.lower().strip()
        existing = db.scalar(select(User).where(User.email == email))
        if existing:
            return
        user = User(
            email=email,
            password_hash=hash_password(settings.auth_password),
            fullname=settings.auth_display_name,
            role="user",
            is_active=True,
        )
        db.add(user)
        db.commit()


def _migrate_legacy_seed_user(db: Session, hash_password) -> None:
    """Keep the original seed account when renaming Lyra → Alder."""
    from app.models.user import User

    target = settings.auth_email.lower().strip()
    legacy_emails = ("user@lyra.ai", "user@alder.local")
    if target in legacy_emails:
        return
    for old_email in legacy_emails:
        legacy = db.scalar(select(User).where(User.email == old_email))
        if not legacy:
            continue
        taken = db.scalar(select(User).where(User.email == target))
        if taken and taken.id != legacy.id:
            continue
        legacy.email = target
        legacy.password_hash = hash_password(settings.auth_password)
        db.commit()
        return


def _ensure_message_sources_column() -> None:
    inspector = inspect(engine)
    if "messages" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("messages")}
    if "sources" in columns:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE messages ADD COLUMN sources TEXT"))


def _ensure_user_system_prompt_column() -> None:
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("users")}
    if "system_prompt" in columns:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN system_prompt TEXT"))
