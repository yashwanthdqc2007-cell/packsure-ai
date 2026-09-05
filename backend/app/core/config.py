"""
Application configuration — reads from environment variables via pydantic-settings.

TODO (Backend Dev):
- Add all required config fields
- Validate on startup
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    gemini_api_key: str = ""
    supabase_url: str = ""
    supabase_anon_key: str = ""
    database_url: str = ""
    frontend_url: str = "http://localhost:5173"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
