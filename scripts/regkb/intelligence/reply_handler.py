"""
IMAP reply handler for processing document download requests.

Polls IMAP for replies to digest emails and processes download requests.
"""

import email
import imaplib
import logging
import os
import re
import ssl
from dataclasses import dataclass, field
from datetime import datetime
from email.header import decode_header
from typing import List, Optional, Tuple

from ..config import config
from .digest_tracker import DigestEntry, digest_tracker
from .url_resolver import url_resolver

logger = logging.getLogger(__name__)


@dataclass
class DownloadRequest:
    """A parsed download request from an email reply."""

    entry_ids: List[str]
    requester_email: str
    subject: str
    received_at: datetime
    raw_body: str


@dataclass
class ProcessedDownload:
    """Result of processing a download request."""

    entry: DigestEntry
    success: bool
    kb_doc_id: Optional[int] = None
    resolved_url: Optional[str] = None
    error: Optional[str] = None
    needs_manual_url: bool = False


@dataclass
class ProcessingResult:
    """Overall result of processing download requests."""

    requests_processed: int = 0
    successful: List[ProcessedDownload] = field(default_factory=list)
    failed: List[ProcessedDownload] = field(default_factory=list)
    needs_manual: List[ProcessedDownload] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class IMAPConfig:
    """IMAP configuration."""

    def __init__(self):
        self.server = config.get("intelligence.reply_processing.imap_server", "imap.gmail.com")
        self.port = config.get("intelligence.reply_processing.imap_port", 993)
        self.username = os.environ.get("IMAP_USERNAME") or os.environ.get("SMTP_USERNAME")
        self.password = os.environ.get("IMAP_PASSWORD") or os.environ.get("SMTP_PASSWORD")
        self.poll_interval = config.get("intelligence.reply_processing.poll_interval", 30)

    @property
    def is_configured(self) -> bool:
        """Check if IMAP is properly configured."""
        return bool(self.username and self.password)


class ReplyHandler:
    """Handles IMAP polling and reply processing."""

    # Subject patterns to match digest replies
    SUBJECT_PATTERNS = [
        r"Re:\s*Regulatory Intelligence Weekly",
        r"Re:\s*Regulatory Intelligence Digest",
        r"Re:\s*RegKB Weekly",
    ]

    # Patterns to extract entry IDs from email body
    ID_PATTERNS = [
        # "Download: 07, 12, 15" or "download: 07, 12"
        r"(?:download|get|fetch)[:\s]+([0-9,\s\-]+)",
        # Just numbers separated by commas/spaces
        r"^([0-9]{1,2}(?:[,\s]+[0-9]{1,2})+)\s*$",
        # Full IDs like "2026-0125-07, 2026-0125-12"
        r"(\d{4}-\d{4}-\d{2}(?:[,\s]+\d{4}-\d{4}-\d{2})+)",
        # Single number on its own line
        r"^([0-9]{1,2})\s*$",
    ]

    def __init__(self) -> None:
        """Initialize the reply handler."""
        self.config = IMAPConfig()
        self._connection: Optional[imaplib.IMAP4_SSL] = None

        # Get allowed senders (recipients list from config)
        self.allowed_senders = set(
            email.lower() for email in
            config.get("intelligence.email.recipients", [])
        )

    def _connect(self) -> Tuple[bool, Optional[str]]:
        """
        Connect to the IMAP server.

        Returns:
            Tuple of (success, error_message).
        """
        if not self.config.is_configured:
            return False, "IMAP credentials not configured"

        try:
            context = ssl.create_default_context()
            self._connection = imaplib.IMAP4_SSL(
                self.config.server,
                self.config.port,
                ssl_context=context,
            )
            self._connection.login(self.config.username, self.config.password)
            logger.info(f"Connected to IMAP server: {self.config.server}")
            return True, None

        except imaplib.IMAP4.error as e:
            return False, f"IMAP login failed: {str(e)}"
        except Exception as e:
            return False, f"IMAP connection failed: {str(e)}"

    def _disconnect(self) -> None:
        """Disconnect from the IMAP server."""
        if self._connection:
            try:
                self._connection.logout()
            except Exception:
                pass
            self._connection = None

    def _decode_header_value(self, value: str) -> str:
        """Decode an email header value."""
        if not value:
            return ""

        decoded_parts = []
        for part, charset in decode_header(value):
            if isinstance(part, bytes):
                charset = charset or "utf-8"
                try:
                    decoded_parts.append(part.decode(charset, errors="replace"))
                except Exception:
                    decoded_parts.append(part.decode("utf-8", errors="replace"))
            else:
                decoded_parts.append(part)

        return " ".join(decoded_parts)

    def _get_email_body(self, msg: email.message.Message) -> str:
        """Extract the plain text body from an email."""
        body = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        try:
                            body = payload.decode(charset, errors="replace")
                        except Exception:
                            body = payload.decode("utf-8", errors="replace")
                        break
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                try:
                    body = payload.decode(charset, errors="replace")
                except Exception:
                    body = payload.decode("utf-8", errors="replace")

        return body

    def _parse_entry_ids(self, body: str) -> List[str]:
        """
        Parse entry IDs from email body.

        Args:
            body: Email body text.

        Returns:
            List of entry ID strings.
        """
        entry_ids = []

        # Clean the body - get first meaningful lines
        lines = body.strip().split("\n")
        # Take first 10 non-empty lines (to avoid parsing quoted content)
        relevant_lines = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith(">"):  # Skip quoted content
                relevant_lines.append(line)
                if len(relevant_lines) >= 10:
                    break

        text = "\n".join(relevant_lines)

        # Try each pattern
        for pattern in self.ID_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            if matches:
                for match in matches:
                    # Split by comma, space, or semicolon
                    ids = re.split(r"[,;\s]+", match)
                    for id_str in ids:
                        id_str = id_str.strip()
                        if id_str and re.match(r"^(\d{1,2}|\d{4}-\d{4}-\d{2})$", id_str):
                            entry_ids.append(id_str)

        # Deduplicate while preserving order
        seen = set()
        unique_ids = []
        for id_str in entry_ids:
            if id_str not in seen:
                seen.add(id_str)
                unique_ids.append(id_str)

        return unique_ids

    def _is_digest_reply(self, subject: str) -> bool:
        """Check if subject matches a digest reply pattern."""
        for pattern in self.SUBJECT_PATTERNS:
            if re.search(pattern, subject, re.IGNORECASE):
                return True
        return False

    def _is_allowed_sender(self, from_addr: str) -> bool:
        """Check if sender is in the allowed list."""
        if not self.allowed_senders:
            return True  # No restrictions if list is empty

        # Extract email from "Name <email>" format
        match = re.search(r"<([^>]+)>", from_addr)
        email_addr = match.group(1) if match else from_addr
        email_addr = email_addr.lower().strip()

        return email_addr in self.allowed_senders

    def poll_for_replies(self, mark_read: bool = True) -> List[DownloadRequest]:
        """
        Poll IMAP for digest reply emails.

        Args:
            mark_read: Whether to mark processed emails as read.

        Returns:
            List of DownloadRequest objects.
        """
        requests = []

        success, error = self._connect()
        if not success:
            logger.error(f"IMAP connection failed: {error}")
            return requests

        try:
            # Select inbox
            self._connection.select("INBOX")

            # Search for unread replies to digest emails
            # Using multiple search criteria
            search_criteria = '(UNSEEN SUBJECT "Re: Regulatory Intelligence")'

            status, message_ids = self._connection.search(None, search_criteria)
            if status != "OK":
                logger.warning(f"IMAP search failed: {status}")
                return requests

            ids = message_ids[0].split()
            logger.info(f"Found {len(ids)} potential digest replies")

            for msg_id in ids:
                try:
                    # Fetch the email
                    status, data = self._connection.fetch(msg_id, "(RFC822)")
                    if status != "OK":
                        continue

                    raw_email = data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    # Get headers
                    subject = self._decode_header_value(msg.get("Subject", ""))
                    from_addr = self._decode_header_value(msg.get("From", ""))
                    date_str = msg.get("Date", "")

                    # Verify it's a digest reply
                    if not self._is_digest_reply(subject):
                        logger.debug(f"Skipping non-digest email: {subject}")
                        continue

                    # Verify sender is allowed
                    if not self._is_allowed_sender(from_addr):
                        logger.warning(f"Skipping email from unauthorized sender: {from_addr}")
                        continue

                    # Get body and parse entry IDs
                    body = self._get_email_body(msg)
                    entry_ids = self._parse_entry_ids(body)

                    if entry_ids:
                        # Parse date
                        try:
                            received_at = email.utils.parsedate_to_datetime(date_str)
                        except Exception:
                            received_at = datetime.now()

                        request = DownloadRequest(
                            entry_ids=entry_ids,
                            requester_email=from_addr,
                            subject=subject,
                            received_at=received_at,
                            raw_body=body[:500],  # First 500 chars for reference
                        )
                        requests.append(request)

                        logger.info(
                            f"Found download request from {from_addr}: "
                            f"{len(entry_ids)} entries"
                        )

                        # Mark as read
                        if mark_read:
                            self._connection.store(msg_id, "+FLAGS", "\\Seen")
                    else:
                        logger.debug(f"No entry IDs found in reply from {from_addr}")

                except Exception as e:
                    logger.error(f"Error processing email {msg_id}: {e}")

        except Exception as e:
            logger.error(f"IMAP polling error: {e}")

        finally:
            self._disconnect()

        return requests

    def process_request(self, request: DownloadRequest) -> List[ProcessedDownload]:
        """
        Process a download request.

        Args:
            request: DownloadRequest to process.

        Returns:
            List of ProcessedDownload results.
        """
        results = []

        # Look up entries
        entries = digest_tracker.lookup_entries(request.entry_ids)

        if not entries:
            logger.warning(f"No entries found for IDs: {request.entry_ids}")
            return results

        for entry in entries:
            # Skip already downloaded entries
            if entry.download_status == "downloaded":
                results.append(ProcessedDownload(
                    entry=entry,
                    success=True,
                    kb_doc_id=entry.kb_doc_id,
                    resolved_url=entry.resolved_url,
                ))
                continue

            # Resolve URL if needed
            url = entry.link
            if url:
                resolve_result = url_resolver.resolve(url)

                if resolve_result.needs_manual:
                    # Mark as needing manual URL
                    digest_tracker.update_entry_status(
                        entry.entry_id,
                        "manual_needed",
                        error_message="URL could not be resolved automatically",
                    )
                    results.append(ProcessedDownload(
                        entry=entry,
                        success=False,
                        needs_manual_url=True,
                        error="URL needs manual resolution",
                    ))
                    continue

                if resolve_result.is_paid:
                    digest_tracker.update_entry_status(
                        entry.entry_id,
                        "failed",
                        error_message=f"Paid domain: {resolve_result.domain}",
                    )
                    results.append(ProcessedDownload(
                        entry=entry,
                        success=False,
                        error=f"Paid domain ({resolve_result.domain})",
                    ))
                    continue

                if resolve_result.success and resolve_result.resolved_url:
                    url = resolve_result.resolved_url

            if not url:
                digest_tracker.update_entry_status(
                    entry.entry_id,
                    "failed",
                    error_message="No URL available",
                )
                results.append(ProcessedDownload(
                    entry=entry,
                    success=False,
                    error="No URL available",
                ))
                continue

            # Attempt download
            try:
                from ..importer import importer

                doc_id = importer.import_from_url(
                    url,
                    metadata={
                        "title": entry.title,
                        "source_url": url,
                        "description": f"Downloaded via email reply - {entry.agency}",
                    },
                )

                if doc_id:
                    digest_tracker.update_entry_status(
                        entry.entry_id,
                        "downloaded",
                        kb_doc_id=doc_id,
                        resolved_url=url,
                    )
                    results.append(ProcessedDownload(
                        entry=entry,
                        success=True,
                        kb_doc_id=doc_id,
                        resolved_url=url,
                    ))
                    logger.info(f"Downloaded entry {entry.entry_id} -> KB ID {doc_id}")
                else:
                    digest_tracker.update_entry_status(
                        entry.entry_id,
                        "failed",
                        error_message="Import returned no ID (duplicate or invalid)",
                    )
                    results.append(ProcessedDownload(
                        entry=entry,
                        success=False,
                        error="Import failed (duplicate or invalid file)",
                    ))

            except Exception as e:
                error_msg = str(e)
                digest_tracker.update_entry_status(
                    entry.entry_id,
                    "failed",
                    error_message=error_msg,
                )
                results.append(ProcessedDownload(
                    entry=entry,
                    success=False,
                    error=error_msg,
                ))
                logger.error(f"Download failed for {entry.entry_id}: {e}")

        return results

    def process_all_pending(self, mark_read: bool = True) -> ProcessingResult:
        """
        Poll for replies and process all download requests.

        Args:
            mark_read: Whether to mark processed emails as read.

        Returns:
            ProcessingResult with all outcomes.
        """
        result = ProcessingResult()

        # Poll for replies
        requests = self.poll_for_replies(mark_read=mark_read)
        result.requests_processed = len(requests)

        if not requests:
            logger.info("No download requests found")
            return result

        # Process each request
        for request in requests:
            try:
                downloads = self.process_request(request)

                for download in downloads:
                    if download.success:
                        result.successful.append(download)
                    elif download.needs_manual_url:
                        result.needs_manual.append(download)
                    else:
                        result.failed.append(download)

            except Exception as e:
                error_msg = f"Error processing request: {e}"
                result.errors.append(error_msg)
                logger.error(error_msg)

        logger.info(
            f"Processed {result.requests_processed} requests: "
            f"{len(result.successful)} successful, "
            f"{len(result.failed)} failed, "
            f"{len(result.needs_manual)} need manual URL"
        )

        return result


# Global handler instance
reply_handler = ReplyHandler()
