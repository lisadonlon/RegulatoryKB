"""
PDF text extraction for the Regulatory Knowledge Base.

Handles extracting text from PDF documents and converting to Markdown format.
Supports OCR fallback for scanned PDFs via PyTesseract.
"""

import logging
import re
from pathlib import Path
from typing import Any, Optional

try:
    import pdfplumber
except Exception as e:  # pragma: no cover - exercised via startup/runtime checks
    pdfplumber = None
    _pdfplumber_import_error = e
else:
    _pdfplumber_import_error = None

from .config import config

logger = logging.getLogger(__name__)

# Lazy-loaded OCR availability flag
_ocr_available: Optional[bool] = None


def _check_ocr_available() -> bool:
    """Check whether pytesseract and Pillow are installed and Tesseract is on PATH."""
    global _ocr_available
    if _ocr_available is not None:
        return _ocr_available
    try:
        import pytesseract  # noqa: F401
        from PIL import Image  # noqa: F401

        # Verify Tesseract binary is reachable
        pytesseract.get_tesseract_version()
        _ocr_available = True
    except Exception:
        _ocr_available = False
    return _ocr_available


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

    def extract(
        self,
        pdf_path: Path,
        doc_id: int,
        force_ocr: bool = False,
    ) -> tuple[bool, Optional[Path], Optional[str]]:
        """
        Extract text from a PDF and save as Markdown.

        Args:
            pdf_path: Path to the PDF file.
            doc_id: Document ID for naming the output file.
            force_ocr: If True, OCR every page regardless of text content.

        Returns:
            Tuple of (success, output_path, error_message).
        """
        try:
            output_path = self.output_dir / f"{doc_id}.md"
            text = self._extract_text(pdf_path, force_ocr=force_ocr)
            markdown = self._convert_to_markdown(text, pdf_path.stem)

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(markdown)

            logger.info(f"Extracted text from {pdf_path.name} to {output_path}")
            return True, output_path, None

        except Exception as e:
            error_msg = f"Failed to extract text from {pdf_path}: {e}"
            logger.error(error_msg)
            return False, None, error_msg

    def _extract_text(self, pdf_path: Path, force_ocr: bool = False) -> str:
        """
        Extract raw text from a PDF file.

        If OCR is enabled and a page yields fewer characters than the configured
        threshold, the page is rendered as an image and OCR'd via PyTesseract.

        Args:
            pdf_path: Path to the PDF file.
            force_ocr: OCR every page regardless of text length.

        Returns:
            Extracted text content.
        """
        ocr_enabled = config.get("ocr.enabled", True)
        min_text_length = config.get("ocr.min_text_length", 50)

        text_parts = []
        ocr_page_count = 0

        if pdfplumber is None:
            raise RuntimeError(
                "pdfplumber is not installed. Install project dependencies with: pip install -e ."
            ) from _pdfplumber_import_error

        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text() or ""

                use_ocr = False
                if force_ocr:
                    use_ocr = True
                elif ocr_enabled and len(page_text.strip()) < min_text_length:
                    use_ocr = True

                if use_ocr:
                    ocr_text = self._ocr_page(page)
                    if ocr_text and len(ocr_text.strip()) > len(page_text.strip()):
                        page_text = ocr_text
                        ocr_page_count += 1

                if page_text.strip():
                    text_parts.append(f"<!-- Page {page_num} -->\n{page_text}")

        if ocr_page_count > 0:
            logger.info(f"OCR applied to {ocr_page_count} page(s) in {pdf_path.name}")

        return "\n\n".join(text_parts)

    def _ocr_page(self, page: Any) -> Optional[str]:
        """
        Render a PDF page to an image and OCR it.

        Uses pypdfium2 (bundled with pdfplumber) to render the page, then
        runs pytesseract OCR on the resulting image.

        Args:
            page: A pdfplumber page object.

        Returns:
            OCR'd text or None if OCR is not available.
        """
        if not _check_ocr_available():
            return None

        try:
            import pytesseract

            dpi = config.get("ocr.dpi", 300)
            language = config.get("ocr.language", "eng")

            # Render page to PIL Image via pdfplumber (uses pypdfium2 internally)
            img = page.to_image(resolution=dpi).original

            # Run OCR
            text = pytesseract.image_to_string(img, lang=language)
            return text

        except Exception as e:
            logger.debug(f"OCR failed for page: {e}")
            return None

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
            with open(output_path, encoding="utf-8") as f:
                return f.read()
        return None

    def re_extract(
        self,
        pdf_path: Path,
        doc_id: int,
        force_ocr: bool = False,
    ) -> tuple[bool, Optional[Path], Optional[str]]:
        """
        Re-extract text from a PDF, overwriting any existing extraction.

        Args:
            pdf_path: Path to the PDF file.
            doc_id: Document ID.
            force_ocr: If True, OCR every page regardless of text content.

        Returns:
            Tuple of (success, output_path, error_message).
        """
        output_path = self.output_dir / f"{doc_id}.md"
        if output_path.exists():
            output_path.unlink()

        return self.extract(pdf_path, doc_id, force_ocr=force_ocr)


# Global extractor instance
extractor = TextExtractor()
