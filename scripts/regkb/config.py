"""
Configuration management for the Regulatory Knowledge Base.

Handles loading and accessing configuration from YAML files and environment variables.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class Config:
    """Configuration manager for the Regulatory Knowledge Base system."""

    # Default configuration values
    DEFAULTS: Dict[str, Any] = {
        "paths": {
            "base_dir": None,  # Set dynamically
            "archive": "archive",
            "extracted": "extracted",
            "database": "db/regulatory.db",
            "backups": "db/backups",
            "logs": "logs",
            "pending": "pending",  # Inbox for auto-import
        },
        "document_types": [
            "guidance",
            "standard",
            "regulation",
            "legislation",
            "policy",
            "procedure",
            "report",
            "white_paper",
            "other",
        ],
        "jurisdictions": [
            "EU",
            "FDA",
            "ISO",
            "ICH",
            "UK",
            "Ireland",
            "WHO",
            "Health Canada",
            "TGA",
            "PMDA",
            "Other",
        ],
        "import": {
            "batch_size": 50,
            "skip_duplicates": True,
            "extract_text": True,
        },
        "search": {
            "default_limit": 10,
            "show_latest_only": True,
            "embedding_model": "all-MiniLM-L6-v2",
        },
        "ocr": {
            "enabled": True,
            "language": "eng",
            "min_text_length": 50,
            "dpi": 300,
        },
        "logging": {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "file_enabled": True,
        },
    }

    _instance: Optional["Config"] = None
    _config: Dict[str, Any] = {}
    _base_dir: Optional[Path] = None

    def __new__(cls) -> "Config":
        """Singleton pattern to ensure single configuration instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize configuration if not already done."""
        if self._initialized:
            return
        self._initialized = True
        self._config = self.DEFAULTS.copy()
        self._base_dir = self._find_base_dir()
        self._load_config_file()

    def _find_base_dir(self) -> Path:
        """Find the base directory of the RegulatoryKB installation."""
        # Check environment variable first
        env_base = os.environ.get("REGKB_BASE_DIR")
        if env_base:
            return Path(env_base)

        # Default to the parent of the scripts directory
        current_file = Path(__file__).resolve()
        # scripts/regkb/config.py -> scripts/regkb -> scripts -> base
        return current_file.parent.parent.parent

    def _load_config_file(self) -> None:
        """Load configuration from YAML file if it exists."""
        config_path = self._base_dir / "config" / "config.yaml"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                file_config = yaml.safe_load(f) or {}
                self._merge_config(file_config)

        # Set the base_dir in paths
        self._config["paths"]["base_dir"] = str(self._base_dir)

    def _merge_config(self, new_config: Dict[str, Any]) -> None:
        """Deep merge new configuration into existing configuration."""
        for key, value in new_config.items():
            if key in self._config and isinstance(self._config[key], dict) and isinstance(value, dict):
                self._config[key].update(value)
            else:
                self._config[key] = value

    @property
    def base_dir(self) -> Path:
        """Get the base directory path."""
        return self._base_dir

    @property
    def archive_dir(self) -> Path:
        """Get the archive directory path."""
        return self._base_dir / self._config["paths"]["archive"]

    @property
    def extracted_dir(self) -> Path:
        """Get the extracted text directory path."""
        return self._base_dir / self._config["paths"]["extracted"]

    @property
    def database_path(self) -> Path:
        """Get the database file path."""
        return self._base_dir / self._config["paths"]["database"]

    @property
    def backups_dir(self) -> Path:
        """Get the backups directory path."""
        return self._base_dir / self._config["paths"]["backups"]

    @property
    def logs_dir(self) -> Path:
        """Get the logs directory path."""
        return self._base_dir / self._config["paths"]["logs"]

    @property
    def pending_dir(self) -> Path:
        """Get the pending inbox directory path for auto-import."""
        return self._base_dir / self._config["paths"].get("pending", "pending")

    @property
    def document_types(self) -> List[str]:
        """Get the list of valid document types."""
        return self._config["document_types"]

    @property
    def jurisdictions(self) -> List[str]:
        """Get the list of valid jurisdictions."""
        return self._config["jurisdictions"]

    def validate_document_type(self, doc_type: str) -> tuple[bool, str]:
        """
        Validate a document type against configured types.

        Args:
            doc_type: Document type to validate.

        Returns:
            Tuple of (is_valid, suggestion_or_error)
        """
        if not doc_type:
            return False, "Document type cannot be empty"

        valid_types = [t.lower() for t in self.document_types]
        if doc_type.lower() in valid_types:
            return True, ""

        # Find closest match for suggestion
        from difflib import get_close_matches
        matches = get_close_matches(doc_type.lower(), valid_types, n=1, cutoff=0.6)
        if matches:
            return False, f"Invalid document type '{doc_type}'. Did you mean '{matches[0]}'? Valid types: {', '.join(self.document_types)}"
        return False, f"Invalid document type '{doc_type}'. Valid types: {', '.join(self.document_types)}"

    def validate_jurisdiction(self, jurisdiction: str) -> tuple[bool, str]:
        """
        Validate a jurisdiction against configured jurisdictions.

        Args:
            jurisdiction: Jurisdiction to validate.

        Returns:
            Tuple of (is_valid, suggestion_or_error)
        """
        if not jurisdiction:
            return False, "Jurisdiction cannot be empty"

        valid_jurisdictions = [j.lower() for j in self.jurisdictions]
        if jurisdiction.lower() in valid_jurisdictions:
            return True, ""

        # Find closest match for suggestion
        from difflib import get_close_matches
        matches = get_close_matches(jurisdiction.lower(), valid_jurisdictions, n=1, cutoff=0.6)
        if matches:
            return False, f"Invalid jurisdiction '{jurisdiction}'. Did you mean '{matches[0]}'? Valid jurisdictions: {', '.join(self.jurisdictions)}"
        return False, f"Invalid jurisdiction '{jurisdiction}'. Valid jurisdictions: {', '.join(self.jurisdictions)}"

    def normalize_document_type(self, doc_type: str) -> str:
        """
        Normalize a document type to match configured case.

        Args:
            doc_type: Document type to normalize.

        Returns:
            Normalized document type or 'other' if invalid.
        """
        for valid_type in self.document_types:
            if doc_type.lower() == valid_type.lower():
                return valid_type
        return "other"

    def normalize_jurisdiction(self, jurisdiction: str) -> str:
        """
        Normalize a jurisdiction to match configured case.

        Args:
            jurisdiction: Jurisdiction to normalize.

        Returns:
            Normalized jurisdiction or 'Other' if invalid.
        """
        for valid_jur in self.jurisdictions:
            if jurisdiction.lower() == valid_jur.lower():
                return valid_jur
        return "Other"

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by key.

        Supports dot notation for nested keys (e.g., 'search.default_limit').
        """
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def reload(self) -> None:
        """Reload configuration from file."""
        self._config = self.DEFAULTS.copy()
        self._load_config_file()


# Global configuration instance
config = Config()
