"""
Application configuration — reads from environment variables via pydantic-settings.

TODO (Backend Dev):
- Add all required config fields
- Validate on startup
"""

try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseModel as BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    supabase_url: str = ""
    supabase_anon_key: str = ""
    database_url: str = ""
    frontend_url: str = "http://localhost:5173"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
