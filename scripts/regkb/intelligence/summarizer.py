"""
LLM-powered summarization for regulatory intelligence.

Generates layperson-friendly summaries of regulatory updates using Claude.
"""

import hashlib
import json
import logging
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import config
from .filter import FilteredEntry

logger = logging.getLogger(__name__)

# Cache database for summaries
SUMMARY_CACHE_DB = "intelligence_summaries.db"


@dataclass
class Summary:
    """A generated summary for a regulatory update."""

    entry_title: str
    entry_agency: str
    entry_date: str
    what_happened: str
    why_it_matters: str
    action_needed: str
    full_summary: str
    generated_at: str
    model_used: str


# Prompt templates
SUMMARY_PROMPT_LAYPERSON = """You are a regulatory affairs expert writing for a non-technical business audience.

Summarize this regulatory update in plain English. Avoid jargon - if technical terms are necessary, briefly explain them.

**Regulatory Update:**
- Title: {title}
- Agency/Source: {agency}
- Category: {category}
- Date: {date}

**Provide a summary in this exact format:**

WHAT HAPPENED:
[1-2 sentences describing the update in plain language]

WHY IT MATTERS:
[1-2 sentences explaining the impact for medical device companies]

ACTION NEEDED:
[One of: "No action required - informational only" OR specific action items]

Keep each section brief and focused. Total response should be under 150 words."""

SUMMARY_PROMPT_TECHNICAL = """You are a regulatory affairs specialist writing for QA/RA professionals.

Provide a technical summary of this regulatory update.

**Regulatory Update:**
- Title: {title}
- Agency/Source: {agency}
- Category: {category}
- Date: {date}

**Provide a summary in this exact format:**

WHAT HAPPENED:
[Technical description of the regulatory change]

WHY IT MATTERS:
[Compliance implications and affected requirements]

ACTION NEEDED:
[Specific compliance actions or "Monitor only"]

Be precise with regulatory terminology. Total response should be under 150 words."""

SUMMARY_PROMPT_BRIEF = """Summarize this regulatory update in one sentence:

Title: {title}
Agency: {agency}
Category: {category}

Provide a single sentence (max 30 words) that captures the key point."""


class Summarizer:
    """Generates summaries for regulatory updates using Claude."""

    def __init__(self) -> None:
        """Initialize the summarizer."""
        self.cache_db_path = config.base_dir / "db" / SUMMARY_CACHE_DB
        self._init_cache_db()
        self._client = None

        # Get config settings
        self.provider = config.get("intelligence.summarization.provider", "anthropic")
        self.model = config.get("intelligence.summarization.model", "claude-3-5-haiku-latest")
        self.style = config.get("intelligence.summarization.style", "layperson")
        self.max_length = config.get("intelligence.summarization.max_length", 200)

    def _init_cache_db(self) -> None:
        """Initialize the summary cache database."""
        self.cache_db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.cache_db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_hash TEXT UNIQUE NOT NULL,
                entry_title TEXT NOT NULL,
                entry_agency TEXT,
                entry_date TEXT,
                what_happened TEXT,
                why_it_matters TEXT,
                action_needed TEXT,
                full_summary TEXT,
                style TEXT,
                model_used TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_summaries_hash ON summaries(entry_hash)")
        conn.commit()
        conn.close()

    def _get_client(self):
        """Get or create the Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                # Check for API key
                api_key = os.environ.get("ANTHROPIC_API_KEY")
                if not api_key:
                    raise ValueError(
                        "ANTHROPIC_API_KEY environment variable not set. "
                        "Set it with: set ANTHROPIC_API_KEY=your-api-key"
                    )
                self._client = anthropic.Anthropic(api_key=api_key)
            except ImportError:
                raise ImportError(
                    "anthropic package not installed. "
                    "Install with: pip install anthropic"
                )
        return self._client

    def _get_entry_hash(self, entry: FilteredEntry) -> str:
        """Generate a unique hash for an entry."""
        content = f"{entry.entry.title}|{entry.entry.agency}|{entry.entry.date}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _get_cached_summary(self, entry_hash: str, style: str) -> Optional[Summary]:
        """Check if a summary is cached."""
        conn = sqlite3.connect(self.cache_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM summaries WHERE entry_hash = ? AND style = ?",
            (entry_hash, style),
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            return Summary(
                entry_title=row["entry_title"],
                entry_agency=row["entry_agency"] or "",
                entry_date=row["entry_date"] or "",
                what_happened=row["what_happened"] or "",
                why_it_matters=row["why_it_matters"] or "",
                action_needed=row["action_needed"] or "",
                full_summary=row["full_summary"] or "",
                generated_at=row["created_at"],
                model_used=row["model_used"] or "",
            )
        return None

    def _cache_summary(
        self,
        entry_hash: str,
        entry: FilteredEntry,
        summary: Summary,
        style: str,
    ) -> None:
        """Cache a generated summary."""
        conn = sqlite3.connect(self.cache_db_path)
        conn.execute(
            """
            INSERT OR REPLACE INTO summaries
            (entry_hash, entry_title, entry_agency, entry_date, what_happened,
             why_it_matters, action_needed, full_summary, style, model_used, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry_hash,
                entry.entry.title,
                entry.entry.agency,
                entry.entry.date,
                summary.what_happened,
                summary.why_it_matters,
                summary.action_needed,
                summary.full_summary,
                style,
                summary.model_used,
                summary.generated_at,
            ),
        )
        conn.commit()
        conn.close()

    def _get_prompt(self, entry: FilteredEntry, style: str) -> str:
        """Get the appropriate prompt template."""
        templates = {
            "layperson": SUMMARY_PROMPT_LAYPERSON,
            "technical": SUMMARY_PROMPT_TECHNICAL,
            "brief": SUMMARY_PROMPT_BRIEF,
        }
        template = templates.get(style, SUMMARY_PROMPT_LAYPERSON)

        return template.format(
            title=entry.entry.title,
            agency=entry.entry.agency or "Unknown",
            category=entry.entry.category or "General",
            date=entry.entry.date or "Recent",
        )

    def _parse_summary_response(self, response_text: str, entry: FilteredEntry, model: str) -> Summary:
        """Parse the LLM response into a Summary object."""
        # Default values
        what_happened = ""
        why_it_matters = ""
        action_needed = "Information only"

        # Parse sections
        lines = response_text.strip().split("\n")
        current_section = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.upper().startswith("WHAT HAPPENED"):
                current_section = "what"
                continue
            elif line.upper().startswith("WHY IT MATTERS"):
                current_section = "why"
                continue
            elif line.upper().startswith("ACTION NEEDED"):
                current_section = "action"
                continue

            if current_section == "what":
                what_happened += line + " "
            elif current_section == "why":
                why_it_matters += line + " "
            elif current_section == "action":
                action_needed += line + " "

        # Clean up
        what_happened = what_happened.strip()
        why_it_matters = why_it_matters.strip()
        action_needed = action_needed.strip() or "Information only"

        return Summary(
            entry_title=entry.entry.title,
            entry_agency=entry.entry.agency or "",
            entry_date=entry.entry.date or "",
            what_happened=what_happened,
            why_it_matters=why_it_matters,
            action_needed=action_needed,
            full_summary=response_text.strip(),
            generated_at=datetime.now().isoformat(),
            model_used=model,
        )

    def summarize(
        self,
        entry: FilteredEntry,
        style: Optional[str] = None,
        use_cache: bool = True,
    ) -> Summary:
        """
        Generate a summary for a regulatory update.

        Args:
            entry: The filtered entry to summarize.
            style: Summary style (layperson, technical, brief).
            use_cache: Whether to use cached summaries.

        Returns:
            Summary object with generated content.
        """
        style = style or self.style
        entry_hash = self._get_entry_hash(entry)

        # Check cache first
        if use_cache:
            cached = self._get_cached_summary(entry_hash, style)
            if cached:
                logger.debug(f"Using cached summary for: {entry.entry.title[:50]}")
                return cached

        # Generate new summary
        client = self._get_client()
        prompt = self._get_prompt(entry, style)

        logger.info(f"Generating {style} summary for: {entry.entry.title[:50]}")

        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = response.content[0].text
            summary = self._parse_summary_response(response_text, entry, self.model)

            # Cache the result
            self._cache_summary(entry_hash, entry, summary, style)

            return summary

        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            # Return a fallback summary
            return Summary(
                entry_title=entry.entry.title,
                entry_agency=entry.entry.agency or "",
                entry_date=entry.entry.date or "",
                what_happened=f"[Summary unavailable: {str(e)[:50]}]",
                why_it_matters="Review the original source for details.",
                action_needed="Manual review recommended",
                full_summary="",
                generated_at=datetime.now().isoformat(),
                model_used="none",
            )

    def summarize_batch(
        self,
        entries: List[FilteredEntry],
        style: Optional[str] = None,
        use_cache: bool = True,
        progress_callback: Optional[callable] = None,
    ) -> List[Summary]:
        """
        Generate summaries for multiple entries.

        Args:
            entries: List of filtered entries to summarize.
            style: Summary style.
            use_cache: Whether to use cached summaries.
            progress_callback: Optional callback(current, total, entry_title).

        Returns:
            List of Summary objects.
        """
        summaries = []
        total = len(entries)

        for i, entry in enumerate(entries):
            if progress_callback:
                progress_callback(i + 1, total, entry.entry.title)

            summary = self.summarize(entry, style, use_cache)
            summaries.append(summary)

        return summaries

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about cached summaries."""
        conn = sqlite3.connect(self.cache_db_path)
        cursor = conn.execute("SELECT COUNT(*), style FROM summaries GROUP BY style")
        by_style = {row[1]: row[0] for row in cursor.fetchall()}

        cursor = conn.execute("SELECT COUNT(*) FROM summaries")
        total = cursor.fetchone()[0]

        conn.close()

        return {"total": total, "by_style": by_style}

    def clear_cache(self) -> int:
        """Clear all cached summaries."""
        conn = sqlite3.connect(self.cache_db_path)
        cursor = conn.execute("DELETE FROM summaries")
        count = cursor.rowcount
        conn.commit()
        conn.close()
        return count


# Global summarizer instance
summarizer = Summarizer()
