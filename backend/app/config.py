"""App settings, read from environment variables (see .env.example)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Everything configurable lives here so nothing secret ends up in the repo (SE5)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://autoapply:autoapply@localhost:5432/autoapply"
    upload_dir: str = "uploads"
    frontend_origin: str = "http://localhost:5173"

    # defaults for new users
    default_confidence_threshold: int = 90  # US7
    default_daily_limit: int = 25  # US16
    max_resume_mb: int = 5  # F2

    # TODO(US1): Google OAuth client id / secret go here once sign in is built
    google_client_id: str = ""
    google_client_secret: str = ""

    # TODO(US13): LLM key for drafting answers
    llm_api_key: str = ""


settings = Settings()
