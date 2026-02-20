"""
Dependency injection and utilities for web routes.
"""

from functools import lru_cache

from fastapi import Request

from regkb.services import get_config as service_get_config
from regkb.services import get_db as service_get_db
from regkb.services import get_importer as service_get_importer
from regkb.services import get_search_engine as service_get_search_engine


@lru_cache
def get_db():
    """Get cached database instance."""
    return service_get_db()


@lru_cache
def get_search_engine():
    """Get cached search engine instance."""
    return service_get_search_engine()


@lru_cache
def get_importer():
    """Get cached importer instance."""
    return service_get_importer()


def get_config():
    """Get config singleton."""
    return service_get_config()


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
