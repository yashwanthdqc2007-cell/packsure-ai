"""
PackSure AI — FastAPI Dependency Injection Layer.

Provides clean dependency providers for database repository, storage, and authentication.
Allows seamless test overrides using FastAPI's dependency_overrides dictionary.
"""

from app.database.connection import BaseScanRepository, get_repository


def get_db_repository() -> BaseScanRepository:
    """Dependency provider for database repository operations."""
    return get_repository()
