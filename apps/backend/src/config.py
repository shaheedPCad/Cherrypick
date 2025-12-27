"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str

    # ChromaDB - Supports both URL-based (new) and host/port (legacy) config
    chroma_url: str | None = None
    chroma_host: str = "localhost"
    chroma_port: int = 8000

    # Ollama
    ollama_base_url: str = "http://localhost:11434"

    # Application
    app_name: str = "Cherrypick API"
    debug: bool = False

    # CORS
    frontend_cors_origin: str = "http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @property
    def chroma_base_url(self) -> str:
        """Build ChromaDB URL from env vars.

        Prefers CHROMA_URL if set, otherwise constructs from host/port.
        This provides backward compatibility with existing configurations.
        """
        if self.chroma_url:
            return self.chroma_url
        return f"http://{self.chroma_host}:{self.chroma_port}"


# Global settings instance
settings = Settings()
