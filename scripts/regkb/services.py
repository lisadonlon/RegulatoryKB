"""Shared service accessors for core RegKB components.

Provides a single place to retrieve configured singleton-backed services.
This keeps entrypoints decoupled from direct module-level imports and
enables incremental migration to explicit dependency injection.
"""

from .config import config


def get_config():
    """Return application configuration instance."""
    return config


def get_db():
    """Return database service instance."""
    from .database import db

    return db


def get_extractor():
    """Return text extraction service instance."""
    from .extraction import extractor

    return extractor


def get_importer():
    """Return document importer service instance."""
    from .importer import importer

    return importer


def get_downloader():
    """Return downloader service instance."""
    from .downloader import downloader

    return downloader


def get_search_engine():
    """Return search engine service instance."""
    from .search import search_engine

    return search_engine
