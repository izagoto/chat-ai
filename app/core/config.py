from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Local Secure AI"
    host: str = "127.0.0.1"
    port: int = 8000

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2:1b"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_timeout_seconds: float = 120.0

    docs_path: str = "docs"
    rag_top_k: int = 3
    rag_chunk_size: int = 800
    rag_chunk_overlap: int = 120
    session_max_turns: int = 12

    # Empty = auth disabled. Set LOCAL_API_KEY to require X-API-Key.
    local_api_key: str = ""
    cors_origins: list[str] = [
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    ]
    default_safety_mode: str = "normal"


settings = Settings()
