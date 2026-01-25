"""
PDF text extraction for the Regulatory Knowledge Base.

Handles extracting text from PDF documents and converting to Markdown format.
"""

import logging
import re
from pathlib import Path
from typing import Optional, Tuple

import fitz  # PyMuPDF

from .config import config

logger = logging.getLogger(__name__)


class TextExtractor:
    """Extracts text from PDF documents and converts to Markdown."""

    def __init__(self, output_dir: Optional[Path] = None) -> None:
        """
        Initialize the text extractor.

        Args:
            output_dir: Directory for extracted text files. Uses config default if not provided.
        """
        self.output_dir = output_dir or config.extracted_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def extract(self, pdf_path: Path, doc_id: int) -> Tuple[bool, Optional[Path], Optional[str]]:
        """
        Extract text from a PDF and save as Markdown.

        Args:
            pdf_path: Path to the PDF file.
            doc_id: Document ID for naming the output file.

        Returns:
            Tuple of (success, output_path, error_message).
        """
        try:
            output_path = self.output_dir / f"{doc_id}.md"
            text = self._extract_text(pdf_path)
            markdown = self._convert_to_markdown(text, pdf_path.stem)

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(markdown)

            logger.info(f"Extracted text from {pdf_path.name} to {output_path}")
            return True, output_path, None

        except Exception as e:
            error_msg = f"Failed to extract text from {pdf_path}: {e}"
            logger.error(error_msg)
            return False, None, error_msg

    def _extract_text(self, pdf_path: Path) -> str:
        """
        Extract raw text from a PDF file.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            Extracted text content.
        """
        doc = fitz.open(pdf_path)
        text_parts = []

        for page_num, page in enumerate(doc, 1):
            page_text = page.get_text("text")
            if page_text.strip():
                text_parts.append(f"<!-- Page {page_num} -->\n{page_text}")

        doc.close()
        return "\n\n".join(text_parts)

    def _convert_to_markdown(self, text: str, title: str) -> str:
        """
        Convert extracted text to Markdown format.

        Args:
            text: Raw extracted text.
            title: Document title for the header.

        Returns:
            Markdown formatted text.
        """
        # Add title
        markdown = f"# {title}\n\n"

        # Process the text
        lines = text.split("\n")
        processed_lines = []
        in_list = False

        for line in lines:
            stripped = line.strip()

            # Skip empty lines but preserve paragraph breaks
            if not stripped:
                if processed_lines and processed_lines[-1] != "":
                    processed_lines.append("")
                in_list = False
                continue

            # Detect potential headings (all caps lines, short lines ending with no punctuation)
            if self._is_potential_heading(stripped):
                if processed_lines and processed_lines[-1] != "":
                    processed_lines.append("")
                processed_lines.append(f"## {stripped}")
                processed_lines.append("")
                in_list = False
                continue

            # Detect list items
            if self._is_list_item(stripped):
                processed_lines.append(self._format_list_item(stripped))
                in_list = True
                continue

            # Regular paragraph text
            if in_list and not self._is_list_item(stripped):
                processed_lines.append("")
                in_list = False

            processed_lines.append(stripped)

        markdown += "\n".join(processed_lines)

        # Clean up multiple consecutive blank lines
        markdown = re.sub(r"\n{3,}", "\n\n", markdown)

        return markdown

    def _is_potential_heading(self, line: str) -> bool:
        """Check if a line appears to be a heading."""
        # All caps and relatively short
        if line.isupper() and len(line) < 100 and len(line) > 2:
            return True

        # Numbered section headers (e.g., "1. Introduction", "2.1 Scope")
        if re.match(r"^\d+(\.\d+)*\.?\s+[A-Z]", line) and len(line) < 100:
            return True

        return False

    def _is_list_item(self, line: str) -> bool:
        """Check if a line appears to be a list item."""
        patterns = [
            r"^[\u2022\u2023\u25E6\u2043\u2219]\s",  # Bullet characters
            r"^[-*+]\s",  # Markdown-style bullets
            r"^\d+[.)]\s",  # Numbered lists
            r"^[a-z][.)]\s",  # Lettered lists
            r"^\([a-z0-9]+\)\s",  # Parenthetical lists
        ]
        return any(re.match(p, line) for p in patterns)

    def _format_list_item(self, line: str) -> str:
        """Format a line as a Markdown list item."""
        # Convert various bullet styles to standard Markdown
        line = re.sub(r"^[\u2022\u2023\u25E6\u2043\u2219]\s*", "- ", line)
        line = re.sub(r"^[*+]\s*", "- ", line)

        # Keep numbered lists as-is but ensure proper formatting
        if re.match(r"^\d+[.)]\s", line):
            line = re.sub(r"^(\d+)[.)]\s*", r"\1. ", line)

        return line

    def get_extracted_text(self, doc_id: int) -> Optional[str]:
        """
        Get the extracted text for a document.

        Args:
            doc_id: Document ID.

        Returns:
            Extracted text content or None if not found.
        """
        output_path = self.output_dir / f"{doc_id}.md"
        if output_path.exists():
            with open(output_path, "r", encoding="utf-8") as f:
                return f.read()
        return None

    def re_extract(self, pdf_path: Path, doc_id: int) -> Tuple[bool, Optional[Path], Optional[str]]:
        """
        Re-extract text from a PDF, overwriting any existing extraction.

        Args:
            pdf_path: Path to the PDF file.
            doc_id: Document ID.

        Returns:
            Tuple of (success, output_path, error_message).
        """
        output_path = self.output_dir / f"{doc_id}.md"
        if output_path.exists():
            output_path.unlink()

        return self.extract(pdf_path, doc_id)


# Global extractor instance
extractor = TextExtractor()
