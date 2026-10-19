"""Configuration settings for Provenance using Pydantic Settings."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Runtime configuration for Provenance agent and services."""

    llm_model: str = "gemma4:12b"
    ollama_base_url: str = "http://localhost:11434/v1"
    temperature: float = 0.1
    embedding_model: str = "BAAI/bge-small-en-v1.5"

    groq_api_key: Optional[str] = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "openai/gpt-oss-120b"
    auto_detect_local: bool = True

    project_root: Path = Path(__file__).resolve().parent.parent.parent
    kb_dir: Path = project_root / "data" / "kb"
    indexes_dir: Path = project_root / "data" / "indexes"
    db_path: Path = project_root / "data" / "audit.db"
    manifest_path: Path = project_root / "eval" / "test_injected_manifest.json"

    top_k_retrieval: int = 5
    rrf_k: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()
