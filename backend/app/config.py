"""
Support Brain - Configuration & Environment Validation
Loads and validates all required environment variables at startup.
"""
from pydantic_settings import BaseSettings
from pydantic import Field, validator
from functools import lru_cache
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # AI Provider & Models (Ollama or Gemini)
    LLM_PROVIDER: str = Field(
        default="ollama",
        description="Text generation provider ('gemini' or 'ollama')"
    )
    OLLAMA_BASE_URL: str = Field(
        default="http://localhost:11434",
        description="Ollama local/cloud server endpoint"
    )
    OLLAMA_MODEL: str = Field(
        default="gemma4:31b-cloud",
        description="Ollama model tag to use for generation"
    )

    # Gemini AI
    GEMINI_API_KEY: str = Field(..., description="Google Gemini API Key")
    GEMINI_MODEL: str = Field(
        default="gemini-3.8-flash",
        description="Gemini text generation model"
    )
    GEMINI_EMBEDDING_MODEL: str = Field(
        default="gemini-embedding-001",
        description="Gemini embedding model for vector search"
    )

    # Database
    DATABASE_URL: str = Field(..., description="PostgreSQL connection string with pgvector")

    # Gmail OAuth
    GMAIL_CLIENT_ID: str = Field(..., description="Google OAuth2 Client ID")
    GMAIL_CLIENT_SECRET: str = Field(..., description="Google OAuth2 Client Secret")
    GMAIL_REDIRECT_URI: str = Field(..., description="OAuth2 redirect URI")

    # App Security
    APP_SECRET_KEY: str = Field(..., description="JWT signing secret — keep this strong")
    TOKEN_ENCRYPTION_KEY: str = Field(..., description="Fernet key for Gmail token encryption")

    # URLs
    FRONTEND_URL: str = Field(default="http://localhost:5173", description="Frontend base URL")
    BACKEND_URL: str = Field(default="http://localhost:8000", description="Backend base URL")

    # JWT Settings
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Upload limits
    MAX_UPLOAD_SIZE_MB: int = 10
    CHUNK_SIZE: int = 500         # tokens per knowledge chunk
    CHUNK_OVERLAP: int = 50       # overlap between chunks

    # AI confidence
    SIMILARITY_THRESHOLD: float = 0.45   # cosine similarity cutoff
    TOP_K_CHUNKS: int = 5                # number of knowledge chunks to retrieve

    # Rate limiting (public chat)
    CHAT_RATE_LIMIT: str = "30/minute"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"

    def validate_all(self) -> None:
        """Called at startup — logs which optional vars use defaults."""
        required = [
            "GEMINI_API_KEY", "DATABASE_URL", "GMAIL_CLIENT_ID",
            "GMAIL_CLIENT_SECRET", "GMAIL_REDIRECT_URI",
            "APP_SECRET_KEY", "TOKEN_ENCRYPTION_KEY"
        ]
        for var in required:
            value = getattr(self, var, None)
            if not value or value.startswith("your_"):
                raise ValueError(
                    f"❌ Environment variable {var} is missing or still a placeholder. "
                    f"Please set a real value in backend/.env"
                )
        logger.info("✅ All required environment variables validated.")
        logger.info(f"   LLM_PROVIDER        = {self.LLM_PROVIDER}")
        if self.LLM_PROVIDER == "ollama":
            logger.info(f"   OLLAMA_MODEL        = {self.OLLAMA_MODEL} ({self.OLLAMA_BASE_URL})")
        else:
            logger.info(f"   GEMINI_MODEL        = {self.GEMINI_MODEL}")
        logger.info(f"   GEMINI_EMBEDDING    = {self.GEMINI_EMBEDDING_MODEL}")
        logger.info(f"   FRONTEND_URL        = {self.FRONTEND_URL}")
        logger.info(f"   BACKEND_URL         = {self.BACKEND_URL}")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
