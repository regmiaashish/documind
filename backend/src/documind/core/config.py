"""Validated Pydantic v2 settings; environment variables override the root .env."""

from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import Field, HttpUrl, PostgresDsn, SecretStr, UrlConstraints, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[4] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    database_url: Annotated[
        PostgresDsn, UrlConstraints(allowed_schemes=["postgresql"], host_required=True)
    ] = Field(default="postgresql://documind:documind@localhost:5432/documind", repr=False)
    gemini_api_key: SecretStr = SecretStr("")
    gemini_base_url: HttpUrl = "https://generativelanguage.googleapis.com/v1beta"
    # These match the migration's vector column; changing them needs re-embedding.
    embedding_model: Literal["gemini-embedding-2"] = "gemini-embedding-2"
    embedding_dimensions: int = Field(default=768, ge=768, le=768)
    chunk_size: int = Field(default=300, ge=300, le=800)
    chunk_overlap: int = Field(default=50, ge=0)
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    max_pdf_pages: int = Field(default=100, gt=0)
    max_extracted_characters: int = Field(default=500_000, gt=0)
    max_chunks: int = Field(default=200, gt=0)
    llm_primary_model: str = Field(default="gemini-3.5-flash-lite", min_length=1)
    llm_fallback_model: str = Field(default="gemini-3.8-flash", min_length=1)
    llm_max_output_tokens: int = Field(default=1024, gt=0, le=4096)
    retrieval_mode: Literal["vector", "hybrid", "hybrid_rerank"] = "hybrid_rerank"
    retrieval_candidates: int = Field(default=12, ge=5, le=30)
    context_top_n: int = Field(default=5, ge=1, le=10)
    similarity_threshold: float = Field(default=0.45, ge=0, le=1)
    request_timeout_seconds: int = Field(default=120, ge=10, le=300)
    agent_max_steps: int = Field(default=3, ge=1, le=5)
    agent_max_tokens: int = Field(default=16000, ge=2048, le=100000)
    agent_max_cost_usd: float = Field(default=0.16, gt=0, le=1)
    agent_token_price_ceiling_usd: float = Field(default=10, gt=0)
    tool_timeout_seconds: float = Field(default=10, gt=0, le=30)

    @model_validator(mode="after")
    def validate_chunking(self) -> Self:
        if self.chunk_size not in (300, 800):
            raise ValueError("chunk_size must be 300 or 800")
        # Uploads support both sizes, so overlap must be safe for the smaller one.
        if self.chunk_overlap >= 300:
            raise ValueError("chunk_overlap must be smaller than 300")
        return self


settings = Settings()
