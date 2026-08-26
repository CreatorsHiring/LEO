from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "LEO Local LLM Workbench"
    data_dir: Path = Field(default=Path("./data"))

    ollama_base_url: str = "http://127.0.0.1:11434"
    router_model: str = "qwen2.5:1.5b-instruct"
    embedding_provider: str = "ollama"
    default_embedding_model: str = "nomic-embed-text"

    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_collection: str = "leo_documents"

    max_upload_mb: int = 50
    chunk_size: int = 1000
    chunk_overlap: int = 180
    retrieval_top_k: int = 5

    class Config:
        env_file = ".env"
        env_prefix = "LEO_"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings
