from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Alder AI"
    host: str = "127.0.0.1"
    port: int = 8000

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2:3b"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_vision_model: str = "llava"
    ollama_timeout_seconds: float = 180.0

    data_path: str = "data"
    documents_path: str = "data/documents"
    docs_path: str = "docs"
    database_url: str = "sqlite:///data/alder.db"
    rag_top_k: int = 5
    rag_chunk_size: int = 800
    rag_chunk_overlap: int = 120
    rag_use_embeddings: bool = True
    rag_embed_min_score: float = 0.55
    rag_keyword_min_score: float = 0.05
    video_frame_interval_sec: float = 5.0
    video_max_frames: int = 20
    session_max_turns: int = 12
    default_collection: str = "default"
    max_upload_bytes: int = 25 * 1024 * 1024
    url_fetch_timeout_seconds: float = 15.0
    url_max_bytes: int = 5 * 1024 * 1024

    # Empty = auth disabled. Set LOCAL_API_KEY to require X-API-Key.
    local_api_key: str = ""
    cors_origins: list[str] = [
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    ]
    default_safety_mode: str = "normal"
    auth_enabled: bool = True
    auth_email: str = "user@alder.ai"
    auth_password: str = "Alder@2026"
    auth_display_name: str = "User"
    auth_secret: str = "alder-change-me"


settings = Settings()
