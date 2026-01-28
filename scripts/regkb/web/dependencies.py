"""
Dependency injection and utilities for web routes.
"""

from functools import lru_cache

from fastapi import Request

from regkb.config import config
from regkb.database import Database
from regkb.importer import DocumentImporter
from regkb.search import SearchEngine


@lru_cache
def get_db() -> Database:
    """Get cached database instance."""
    return Database()


@lru_cache
def get_search_engine() -> SearchEngine:
    """Get cached search engine instance."""
    return SearchEngine()


@lru_cache
def get_importer() -> DocumentImporter:
    """Get cached importer instance."""
    return DocumentImporter()


def get_config():
    """Get config singleton."""
    return config


# Flash message utilities
def flash(request: Request, message: str, category: str = "info") -> None:
    """Add a flash message to the session."""
    if "_flashes" not in request.session:
        request.session["_flashes"] = []
    request.session["_flashes"].append({"category": category, "message": message})


def get_flashed_messages(request: Request) -> list[dict]:
    """Get and clear flash messages from the session."""
    messages = request.session.pop("_flashes", [])
    return messages


def is_htmx_request(request: Request) -> bool:
    """Check if request is from HTMX."""
    return request.headers.get("HX-Request") == "true"
