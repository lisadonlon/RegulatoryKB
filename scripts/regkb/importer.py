"""
Document import functionality for the Regulatory Knowledge Base.

Handles scanning directories, detecting duplicates, and importing PDFs.
"""

import hashlib
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

import requests
from tqdm import tqdm

from .config import config
from .database import db
from .extraction import extractor

logger = logging.getLogger(__name__)


@dataclass
class ImportResult:
    """Results from an import operation."""

    total_files: int = 0
    imported: int = 0
    duplicates: int = 0
    errors: int = 0
    error_details: List[Dict[str, str]] = field(default_factory=list)

    def __str__(self) -> str:
        return (
            f"Import complete: {self.imported} imported, "
            f"{self.duplicates} duplicates skipped, "
            f"{self.errors} errors"
        )


class DocumentImporter:
    """Handles importing documents into the knowledge base."""

    def __init__(self) -> None:
        """Initialize the document importer."""
        self.archive_dir = config.archive_dir
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.last_version_diff = None  # Set after each import if a prior version is detected
        self.last_content_warning = None  # Set after each import if content doesn't match title

    def is_valid_pdf(self, file_path: Path) -> tuple[bool, str]:
        """
        Verify that a file is actually a PDF by checking magic bytes.

        Args:
            file_path: Path to the file to check.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not file_path.exists():
            return False, f"File not found: {file_path}"

        if not file_path.is_file():
            return False, f"Not a file: {file_path}"

        # Check file size (minimum viable PDF is ~67 bytes)
        try:
            size = file_path.stat().st_size
            if size < 67:
                return False, f"File too small to be a valid PDF ({size} bytes)"
            if size == 0:
                return False, "File is empty"
        except OSError as e:
            return False, f"Cannot read file: {e}"

        # Check PDF magic bytes (%PDF)
        try:
            with open(file_path, "rb") as f:
                header = f.read(8)
                if not header.startswith(b"%PDF"):
                    # Provide helpful message about what the file might be
                    if header.startswith(b"<!DOCTYPE") or header.startswith(b"<html"):
                        return False, "File is HTML, not a PDF (may be an error page)"
                    elif header.startswith(b"PK"):
                        return False, "File is a ZIP archive, not a PDF"
                    elif header.startswith(b"\x89PNG"):
                        return False, "File is a PNG image, not a PDF"
                    elif header.startswith(b"\xff\xd8\xff"):
                        return False, "File is a JPEG image, not a PDF"
                    else:
                        return False, f"File does not have PDF header (got: {header[:4]!r})"
        except OSError as e:
            return False, f"Cannot read file header: {e}"

        return True, ""

    def calculate_hash(self, file_path: Path) -> str:
        """
        Calculate SHA-256 hash of a file.

        Args:
            file_path: Path to the file.

        Returns:
            Hex-encoded SHA-256 hash.
        """
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def scan_directory(self, directory: Path, recursive: bool = True) -> List[Path]:
        """
        Scan a directory for PDF files.

        Args:
            directory: Directory to scan.
            recursive: Whether to scan subdirectories.

        Returns:
            List of PDF file paths.
        """
        pattern = "**/*.pdf" if recursive else "*.pdf"
        return list(directory.glob(pattern))

    def import_directory(
        self,
        source_dir: Path,
        recursive: bool = True,
        metadata_callback: Optional[Callable[[Path], Dict[str, str]]] = None,
        progress: bool = True,
    ) -> ImportResult:
        """
        Import all PDFs from a directory.

        Args:
            source_dir: Source directory to scan.
            recursive: Whether to scan subdirectories.
            metadata_callback: Optional callback to get metadata for each file.
            progress: Whether to show progress bar.

        Returns:
            ImportResult with statistics.
        """
        result = ImportResult()
        pdf_files = self.scan_directory(source_dir, recursive)
        result.total_files = len(pdf_files)

        if not pdf_files:
            logger.info(f"No PDF files found in {source_dir}")
            return result

        # Create import batch
        batch_id = db.create_import_batch(str(source_dir))

        iterator = tqdm(pdf_files, desc="Importing", disable=not progress)

        for pdf_path in iterator:
            try:
                # Verify it's actually a PDF
                is_valid, validation_error = self.is_valid_pdf(pdf_path)
                if not is_valid:
                    result.errors += 1
                    result.error_details.append({
                        "file": str(pdf_path),
                        "error": validation_error
                    })
                    logger.warning(f"Skipping invalid file {pdf_path.name}: {validation_error}")
                    continue

                # Calculate hash
                file_hash = self.calculate_hash(pdf_path)

                # Check for duplicate
                if db.document_exists(file_hash):
                    result.duplicates += 1
                    logger.debug(f"Duplicate skipped: {pdf_path.name}")
                    continue

                # Get metadata
                if metadata_callback:
                    metadata = metadata_callback(pdf_path)
                else:
                    metadata = self._default_metadata(pdf_path)

                # Import the document
                success = self._import_single(pdf_path, file_hash, metadata)
                if success:
                    result.imported += 1
                else:
                    result.errors += 1

            except Exception as e:
                result.errors += 1
                result.error_details.append({
                    "file": str(pdf_path),
                    "error": str(e)
                })
                logger.error(f"Error importing {pdf_path}: {e}")

        # Update batch record
        db.update_import_batch(
            batch_id,
            total_files=result.total_files,
            imported=result.imported,
            duplicates=result.duplicates,
            errors=result.errors,
            status="completed"
        )

        return result

    def import_file(
        self,
        file_path: Path,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Optional[int]:
        """
        Import a single file.

        Args:
            file_path: Path to the PDF file.
            metadata: Document metadata.

        Returns:
            Document ID if successful, None otherwise.
        """
        # Verify it's actually a PDF
        is_valid, validation_error = self.is_valid_pdf(file_path)
        if not is_valid:
            logger.error(f"Cannot import {file_path}: {validation_error}")
            return None

        try:
            file_hash = self.calculate_hash(file_path)

            if db.document_exists(file_hash):
                logger.info(f"Document already exists: {file_path.name}")
                return None

            if metadata is None:
                metadata = self._default_metadata(file_path)

            return self._import_single(file_path, file_hash, metadata)

        except Exception as e:
            logger.error(f"Error importing {file_path}: {e}")
            return None

    def import_from_url(
        self,
        url: str,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Optional[int]:
        """
        Download and import a document from a URL.

        Args:
            url: URL to download from.
            metadata: Document metadata.

        Returns:
            Document ID if successful, None otherwise.
        """
        try:
            # Download to temporary location
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            response = requests.get(url, timeout=60, stream=True, headers=headers)
            response.raise_for_status()

            # Determine filename
            if "content-disposition" in response.headers:
                import re
                cd = response.headers["content-disposition"]
                fname_match = re.search(r'filename="?([^";\n]+)"?', cd)
                filename = fname_match.group(1) if fname_match else "downloaded.pdf"
            else:
                filename = url.split("/")[-1].split("?")[0] or "downloaded.pdf"

            if not filename.endswith(".pdf"):
                filename += ".pdf"

            # Save to temp location
            temp_path = config.base_dir / "temp" / filename
            temp_path.parent.mkdir(parents=True, exist_ok=True)

            with open(temp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Verify downloaded file is actually a PDF
            is_valid, validation_error = self.is_valid_pdf(temp_path)
            if not is_valid:
                temp_path.unlink()  # Clean up invalid file
                logger.error(f"Downloaded file from {url} is not a valid PDF: {validation_error}")
                return None

            # Set source URL in metadata
            if metadata is None:
                metadata = self._default_metadata(temp_path)
            metadata["source_url"] = url

            # Import the file
            doc_id = self.import_file(temp_path, metadata)

            # Clean up temp file
            temp_path.unlink()

            return doc_id

        except Exception as e:
            logger.error(f"Error downloading from {url}: {e}")
            return None

    def _import_single(
        self,
        source_path: Path,
        file_hash: str,
        metadata: Dict[str, str],
    ) -> Optional[int]:
        """
        Import a single document (internal method).

        Args:
            source_path: Path to the source PDF.
            file_hash: Pre-calculated file hash.
            metadata: Document metadata.

        Returns:
            Document ID if successful, None otherwise.
        """
        # Determine archive path
        archive_subdir = self.archive_dir / metadata.get("jurisdiction", "Other")
        archive_subdir.mkdir(parents=True, exist_ok=True)

        # Use hash prefix in filename to ensure uniqueness
        archive_filename = f"{file_hash[:8]}_{source_path.name}"
        archive_path = archive_subdir / archive_filename

        # Copy file to archive
        shutil.copy2(source_path, archive_path)

        # Add to database
        doc_id = db.add_document(
            file_hash=file_hash,
            title=metadata.get("title", source_path.stem),
            document_type=metadata.get("document_type", "other"),
            jurisdiction=metadata.get("jurisdiction", "Other"),
            file_path=str(archive_path),
            version=metadata.get("version"),
            source_url=metadata.get("source_url"),
            description=metadata.get("description"),
            download_date=metadata.get("download_date"),
        )

        # Extract text
        if config.get("import.extract_text", True):
            success, extracted_path, _ = extractor.extract(archive_path, doc_id)
            if success and extracted_path:
                db.update_document(doc_id, extracted_path=str(extracted_path))

        # Validate content matches title (advisory, never fails the import)
        self.last_content_warning = None
        try:
            from .version_diff import validate_content_matches_title

            self.last_content_warning = validate_content_matches_title(doc_id)
            if self.last_content_warning:
                logger.warning(f"Content warning for doc {doc_id}: {self.last_content_warning}")
        except Exception as e:
            logger.debug(f"Content validation skipped for doc {doc_id}: {e}")

        # Check for prior version and auto-generate diff (never fail the import)
        self.last_version_diff = None
        try:
            from .version_diff import detect_and_diff

            self.last_version_diff = detect_and_diff(doc_id)
            if self.last_version_diff:
                if self.last_version_diff.auto_superseded:
                    logger.info(
                        f"Prior version detected: [{self.last_version_diff.old_doc_id}] "
                        f"'{self.last_version_diff.old_doc_title}' superseded. "
                        f"Diff similarity: {self.last_version_diff.stats.similarity:.1%}"
                    )
                else:
                    logger.warning(
                        f"Possible prior version [{self.last_version_diff.old_doc_id}] "
                        f"but similarity too low to auto-supersede"
                    )
        except Exception as e:
            logger.error(f"Version detection failed for doc {doc_id}: {e}")

        logger.info(f"Imported: {source_path.name} (ID: {doc_id})")
        return doc_id

    def _default_metadata(self, file_path: Path) -> Dict[str, str]:
        """
        Generate default metadata from filename.

        Args:
            file_path: Path to the PDF file.

        Returns:
            Dictionary of default metadata.
        """
        return {
            "title": file_path.stem.replace("_", " ").replace("-", " "),
            "document_type": "other",
            "jurisdiction": "Other",
        }


# Global importer instance
importer = DocumentImporter()
