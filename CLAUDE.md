# CLAUDE.md — Project Context for Claude Code

## Project Overview

Regulatory Knowledge Base (RegKB) for medical device regulatory affairs.
Python 3.9+, Click CLI, local document management with natural language search.

## Key Commands

```bash
pip install -e .              # Core install
pip install -e ".[dev]"       # Dev tools (pytest, black, ruff, mypy)
pip install -e ".[ocr]"       # OCR support (pytesseract, Pillow)
regkb --help                  # CLI entry point
pytest                        # Run tests
pre-commit run --all-files    # Lint/format check
```

## Architecture

- **Package**: `scripts/regkb/`
- **Entry point**: `regkb.cli:main` (Click CLI)
- **Config**: `config/config.yaml`
- **Build**: setuptools, configured in `pyproject.toml`

## Code Conventions

- **Formatter**: Black, 100-char line length
- **Linter**: Ruff — rule sets: E, F, W, I, N, UP, B, C4 (E501 ignored)
- **Type checker**: MyPy (strict return/config warnings, missing imports ignored)
- **Docstrings**: Google style
- **Type annotations**: Required on all functions
- **Target**: Python 3.9+

## Data Stores

| Store | Location | Purpose |
|-------|----------|---------|
| SQLite | `db/regulatory.db` | Structured metadata |
| ChromaDB | `db/chroma/` | Vector embeddings for search |
| Extracted text | `extracted/` | PDF text extraction output |
| PDF archive | `archive/` | Source document storage |

## Intelligence Module

`scripts/regkb/intelligence/` — automated regulatory monitoring pipeline:

- `fetcher` — source data retrieval
- `filter` — relevance filtering
- `analyzer` — content analysis
- `summarizer` — digest generation
- `emailer` — notification delivery
- `digest_tracker` — deduplication tracking
- `url_resolver` — link resolution
- `reply_handler` — email reply processing
- `scheduler` — job orchestration

## Environment

Secrets live in `.env` (never committed):

- `ANTHROPIC_API_KEY`
- SMTP/IMAP credentials

## Testing

- Framework: pytest (configured in `pyproject.toml`)
- Tests: `tests/`
- Run: `pytest` (verbose, short tracebacks by default)

## Pre-commit

Ruff + Black hooks configured in `.pre-commit-config.yaml`.
Run `pre-commit run --all-files` to check before committing.
