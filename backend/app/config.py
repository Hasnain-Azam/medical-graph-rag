"""
Application configuration — reads from .env file via pydantic-settings.
All environment variables are type-validated at startup.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Google Gemini ────────────────────────────────────────────────────────────
    gemini_api_key: str
    gemini_chat_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 3072  # gemini-embedding-001 produces 3072-dim vectors

    # ── Neo4j ───────────────────────────────────────────────────────────────────
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "medgraph_password"

    # ── Chunking ─────────────────────────────────────────────────────────────────
    chunk_size: int = 2000      # characters per chunk
    chunk_overlap: int = 200    # overlap between chunks

    # ── RAG ─────────────────────────────────────────────────────────────────────
    vector_top_k: int = 5       # top-k similar entities to retrieve
    subgraph_hops: int = 2      # how many hops to expand around seed nodes

    # ── App ─────────────────────────────────────────────────────────────────────
    environment: str = "development"
    log_level: str = "INFO"
    allowed_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton — reads .env once at startup."""
    return Settings()
