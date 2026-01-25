# Regulatory Knowledge Base (RegKB)

A local knowledge base system for managing regulatory documents with natural language search capability.

## Features

- **Document Import**: Scan directories for PDFs, detect duplicates via SHA-256 hash
- **Metadata Management**: Track title, type, jurisdiction, version, source URL
- **Text Extraction**: Convert PDFs to searchable Markdown format
- **Natural Language Search**: Semantic search using sentence transformers + ChromaDB
- **Full-Text Search**: SQLite FTS5 for keyword matching
- **Version Control**: Track document versions, flag latest versions

## Installation

### Prerequisites

- Python 3.9 or higher
- pip (Python package manager)

### Setup

1. Create and activate a virtual environment:

```bash
cd C:\Projects\RegulatoryKB
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate
```

2. Install the package:

```bash
pip install -e .
```

Or install dependencies directly:

```bash
pip install -r requirements.txt
```

## Usage

### Import Documents

Import PDFs from a directory:

```bash
regkb import /path/to/pdfs --recursive
```

Interactive import (prompts for metadata):

```bash
regkb import /path/to/pdfs -i
```

### Search Documents

Natural language search:

```bash
regkb search "MDR Article 120 timeline"
```

Search with filters:

```bash
regkb search "combination product" --type guidance --jurisdiction FDA
```

### Add Single Document

From local file:

```bash
regkb add document.pdf --title "My Document" --type guidance --jurisdiction EU
```

From URL:

```bash
regkb add https://example.com/guidance.pdf
```

### List Documents

```bash
regkb list
regkb list --type standard --jurisdiction ISO
```

### View Document Details

```bash
regkb show 42
```

### Update Document Metadata

```bash
regkb update 42 --title "New Title" --jurisdiction FDA
```

### Statistics

```bash
regkb stats
```

### Database Backup

```bash
regkb backup
```

### Reindex for Search

```bash
regkb reindex
```

## Directory Structure

```
RegulatoryKB/
├── archive/          # Permanent PDF storage (organized by jurisdiction)
├── extracted/        # Markdown text extractions
├── db/
│   ├── regulatory.db # SQLite database
│   ├── chroma/       # ChromaDB vector database
│   └── backups/      # Database backups
├── config/
│   └── config.yaml   # Configuration file
├── logs/             # Application logs
├── scripts/
│   └── regkb/        # Python package
└── .venv/            # Virtual environment
```

## Configuration

Edit `config/config.yaml` to customize:

- Document types and jurisdictions
- Import behavior
- Search settings
- Logging options

## Document Types

Default document types:
- guidance
- standard
- regulation
- legislation
- policy
- procedure
- report
- white_paper
- other

## Jurisdictions

Default jurisdictions:
- EU, FDA, ISO, ICH, UK, Ireland
- WHO, Health Canada, TGA, PMDA
- EMA, MHRA, HPRA, Other

## License

MIT License
