"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str

    # ChromaDB
    chroma_host: str = "localhost"
    chroma_port: int = 8000

    # Ollama
    ollama_base_url: str = "http://localhost:11434"

    # Application
    app_name: str = "Cherrypick API"
    debug: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Global settings instance
settings = Settings()
