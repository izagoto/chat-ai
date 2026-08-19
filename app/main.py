from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import analyze, ask, auth, chat, conversations, documents, health, models, prompt, sessions
from app.core.config import settings
from app.core.logging import RequestContextMiddleware
from app.db.session import init_db
from app.services.ingest_queue import ingest_worker

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
FRONTEND_DIST = FRONTEND_DIR / "dist"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    await ingest_worker.start()
    try:
        yield
    finally:
        await ingest_worker.stop()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.2.0",
        description="Alder AI — on-premise AI chatbot for documents and images (Ollama).",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)

    app.include_router(health.router)
    app.include_router(auth.router, prefix="/v1")
    app.include_router(conversations.router, prefix="/v1")
    app.include_router(models.router, prefix="/v1")
    app.include_router(chat.router, prefix="/v1")
    app.include_router(ask.router, prefix="/v1")
    app.include_router(prompt.router, prefix="/v1")
    app.include_router(documents.router, prefix="/v1")
    app.include_router(analyze.router, prefix="/v1")
    app.include_router(sessions.router, prefix="/v1")

    if FRONTEND_DIST.exists():
        assets_dir = FRONTEND_DIST / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/")
        async def frontend_index() -> FileResponse:
            return FileResponse(FRONTEND_DIST / "index.html")

        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str) -> FileResponse:
            blocked = ("v1/", "docs", "redoc", "openapi.json", "health")
            if full_path.startswith(blocked) or full_path in {"docs", "redoc", "openapi.json", "health"}:
                raise HTTPException(status_code=404, detail="Not found")
            candidate = FRONTEND_DIST / full_path
            if candidate.is_file():
                return FileResponse(candidate)
            index = FRONTEND_DIST / "index.html"
            if index.is_file():
                return FileResponse(index)
            raise HTTPException(status_code=404, detail="Frontend build missing. Run: cd frontend && npm run build")

    return app


app = create_app()
