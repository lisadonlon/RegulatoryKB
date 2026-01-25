"""
Document downloader for acquiring regulatory documents from official sources.
"""

import hashlib
import re
import time
from pathlib import Path
from typing import Optional, Tuple, Callable
from urllib.parse import urlparse, unquote
import requests

from .config import config


class DocumentDownloader:
    """Downloads regulatory documents from official sources."""

    def __init__(self):
        self.download_dir = config.archive_dir
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        })

    def _validate_url(self, url: str) -> Tuple[bool, Optional[str]]:
        """
        Validate URL format before attempting download.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not url:
            return False, "URL cannot be empty"

        if not isinstance(url, str):
            return False, f"URL must be a string, got {type(url).__name__}"

        # Check URL format
        try:
            parsed = urlparse(url)
        except Exception as e:
            return False, f"Invalid URL format: {str(e)}"

        # Validate scheme
        if not parsed.scheme:
            return False, "URL missing scheme (should start with http:// or https://)"
        if parsed.scheme.lower() not in ('http', 'https'):
            return False, f"Unsupported URL scheme '{parsed.scheme}' - only http and https are supported"

        # Validate netloc (domain)
        if not parsed.netloc:
            return False, "URL missing domain name"

        # Basic domain format check
        if '.' not in parsed.netloc and parsed.netloc != 'localhost':
            return False, f"Invalid domain '{parsed.netloc}' - missing top-level domain"

        return True, None

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for filesystem."""
        # Remove or replace invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filename = re.sub(r'\s+', '_', filename)
        filename = filename.strip('._')
        # Limit length
        if len(filename) > 200:
            filename = filename[:200]
        return filename

    def _get_filename_from_url(self, url: str, response: requests.Response) -> str:
        """Extract filename from URL or response headers."""
        # Try Content-Disposition header first
        cd = response.headers.get('Content-Disposition', '')
        if 'filename=' in cd:
            match = re.search(r'filename[*]?=["\']?([^"\';\n]+)', cd)
            if match:
                filename = unquote(match.group(1))
                return self._sanitize_filename(filename)

        # Try URL path
        parsed = urlparse(url)
        path = unquote(parsed.path)
        if path:
            filename = Path(path).name
            if filename and '.' in filename:
                return self._sanitize_filename(filename)

        # Generate from URL hash
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        content_type = response.headers.get('Content-Type', '')
        if 'pdf' in content_type:
            return f"document_{url_hash}.pdf"
        elif 'html' in content_type:
            return f"document_{url_hash}.html"
        return f"document_{url_hash}"

    def download(
        self,
        url: str,
        title: str,
        jurisdiction: str,
        timeout: int = 60,
    ) -> Tuple[bool, Optional[Path], Optional[str]]:
        """
        Download a document from URL.

        Returns:
            Tuple of (success, file_path, error_message)
        """
        # Validate URL first
        is_valid, error = self._validate_url(url)
        if not is_valid:
            return False, None, error

        try:
            # Create jurisdiction subdirectory
            jur_dir = self.download_dir / jurisdiction.lower()
            jur_dir.mkdir(parents=True, exist_ok=True)

            # Download
            response = self.session.get(url, timeout=timeout, allow_redirects=True)
            response.raise_for_status()

            # Determine filename
            original_filename = self._get_filename_from_url(url, response)

            # Create a cleaner filename from title
            safe_title = self._sanitize_filename(title)
            ext = Path(original_filename).suffix or '.pdf'
            if not ext.startswith('.'):
                ext = '.' + ext

            filename = f"{safe_title}{ext}"
            file_path = jur_dir / filename

            # Handle duplicates
            counter = 1
            while file_path.exists():
                filename = f"{safe_title}_{counter}{ext}"
                file_path = jur_dir / filename
                counter += 1

            # Save file
            with open(file_path, 'wb') as f:
                f.write(response.content)

            return True, file_path, None

        except requests.exceptions.Timeout:
            return False, None, f"Timeout downloading {url}"
        except requests.exceptions.HTTPError as e:
            return False, None, f"HTTP error {e.response.status_code}: {url}"
        except requests.exceptions.RequestException as e:
            return False, None, f"Request error: {str(e)}"
        except Exception as e:
            return False, None, f"Error: {str(e)}"

    def download_batch(
        self,
        documents: list,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        delay: float = 1.0,
    ) -> dict:
        """
        Download multiple documents.

        Args:
            documents: List of dicts with 'url', 'title', 'jurisdiction' keys
            progress_callback: Called with (current, total, status_message)
            delay: Seconds to wait between downloads (be nice to servers)

        Returns:
            Dict with 'success', 'failed', 'skipped' lists
        """
        results = {
            'success': [],
            'failed': [],
            'skipped': [],
        }

        total = len(documents)
        for i, doc in enumerate(documents):
            url = doc.get('url', '')
            title = doc.get('title', 'Unknown')
            jurisdiction = doc.get('jurisdiction', 'Other')

            if progress_callback:
                progress_callback(i + 1, total, f"Downloading: {title[:40]}...")

            # Validate URL format first
            is_valid, validation_error = self._validate_url(url)
            if not is_valid:
                results['skipped'].append({
                    'title': title,
                    'url': url,
                    'reason': validation_error
                })
                continue

            # Skip non-downloadable URLs (web pages that need manual handling)
            if url.startswith('https://www.gov.uk/guidance/') or \
               url.startswith('https://www.canada.ca/en/') or \
               url.startswith('https://www.tga.gov.au/'):
                # These are web pages, not direct downloads
                if '.pdf' not in url.lower() and '/download' not in url.lower():
                    results['skipped'].append({
                        'title': title,
                        'url': url,
                        'reason': 'Web page - manual download required'
                    })
                    continue

            success, file_path, error = self.download(url, title, jurisdiction)

            if success:
                results['success'].append({
                    'title': title,
                    'url': url,
                    'file_path': str(file_path),
                    'jurisdiction': jurisdiction,
                })
            else:
                results['failed'].append({
                    'title': title,
                    'url': url,
                    'error': error,
                })

            # Be nice to servers
            if i < total - 1:
                time.sleep(delay)

        return results


# Global instance
downloader = DocumentDownloader()
