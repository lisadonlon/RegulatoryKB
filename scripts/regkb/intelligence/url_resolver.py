"""
URL resolver for social media and aggregator links.

Resolves LinkedIn posts, Twitter links, and other aggregator URLs
to the actual document URLs they reference.
"""

import logging
import re
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple
from urllib.parse import urlparse

import requests

from ..config import config

logger = logging.getLogger(__name__)

# Request settings
REQUEST_TIMEOUT = 15
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Known regulatory domains
DEFAULT_TRUSTED_DOMAINS = [
    "fda.gov",
    "ec.europa.eu",
    "gov.uk",
    "who.int",
    "iso.org",
    "iec.ch",
    "tga.gov.au",
    "canada.ca",
    "pmda.go.jp",
    "hpra.ie",
    "ema.europa.eu",
    "health-products.canada.ca",
    "accessdata.fda.gov",
    "regulations.gov",
    "federalregister.gov",
    "eur-lex.europa.eu",
]

# Social media and aggregator domains that need resolution
SOCIAL_DOMAINS = [
    "linkedin.com",
    "twitter.com",
    "x.com",
    "t.co",
    "lnkd.in",
    "bit.ly",
    "buff.ly",
    "ow.ly",
    "tinyurl.com",
]

# Paid/restricted domains
PAID_DOMAINS = [
    "iso.org",  # ISO standards require purchase
    "iec.ch",  # IEC standards require purchase
    "astm.org",  # ASTM standards require purchase
    "bsigroup.com",  # BSI standards require purchase
]


@dataclass
class ResolveResult:
    """Result of URL resolution."""

    success: bool
    original_url: str
    resolved_url: Optional[str] = None
    document_type: Optional[str] = None  # pdf, html, unknown
    domain: Optional[str] = None
    is_paid: bool = False
    needs_manual: bool = False
    error: Optional[str] = None
    all_links_found: List[str] = None

    def __post_init__(self):
        if self.all_links_found is None:
            self.all_links_found = []


class URLResolver:
    """Resolves social media URLs to actual document URLs."""

    def __init__(self, trusted_domains: Optional[List[str]] = None) -> None:
        """
        Initialize the URL resolver.

        Args:
            trusted_domains: List of trusted regulatory domains.
        """
        self.trusted_domains = set(trusted_domains or DEFAULT_TRUSTED_DOMAINS)

        # Load additional trusted domains from config
        config_domains = config.get("intelligence.reply_processing.trusted_domains", [])
        self.trusted_domains.update(config_domains)

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })

    def _get_domain(self, url: str) -> Optional[str]:
        """Extract the domain from a URL."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www. prefix
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except Exception:
            return None

    def _is_social_url(self, url: str) -> bool:
        """Check if URL is from a social media or aggregator site."""
        domain = self._get_domain(url)
        if not domain:
            return False

        for social in SOCIAL_DOMAINS:
            if social in domain:
                return True
        return False

    def _is_trusted_domain(self, url: str) -> bool:
        """Check if URL is from a trusted regulatory domain."""
        domain = self._get_domain(url)
        if not domain:
            return False

        for trusted in self.trusted_domains:
            if trusted in domain:
                return True
        return False

    def _is_paid_domain(self, url: str) -> bool:
        """Check if URL is from a paid/restricted domain."""
        domain = self._get_domain(url)
        if not domain:
            return False

        for paid in PAID_DOMAINS:
            if paid in domain:
                return True
        return False

    def _detect_document_type(self, url: str, content_type: Optional[str] = None) -> str:
        """Detect the document type from URL or content type."""
        url_lower = url.lower()

        if url_lower.endswith(".pdf"):
            return "pdf"
        if any(url_lower.endswith(ext) for ext in [".doc", ".docx"]):
            return "word"
        if any(url_lower.endswith(ext) for ext in [".xls", ".xlsx"]):
            return "excel"

        if content_type:
            if "pdf" in content_type:
                return "pdf"
            if "html" in content_type:
                return "html"

        return "unknown"

    def _extract_links_from_html(self, html: str, base_url: str) -> List[str]:
        """Extract all links from HTML content."""
        links = []

        # Find href attributes
        href_pattern = r'href=["\']([^"\']+)["\']'
        for match in re.finditer(href_pattern, html, re.IGNORECASE):
            link = match.group(1)
            if link.startswith("http"):
                links.append(link)
            elif link.startswith("/"):
                # Relative URL
                parsed = urlparse(base_url)
                links.append(f"{parsed.scheme}://{parsed.netloc}{link}")

        return links

    def _find_regulatory_links(self, links: List[str]) -> List[str]:
        """Filter links to only regulatory domains."""
        regulatory = []
        for link in links:
            if self._is_trusted_domain(link):
                regulatory.append(link)
        return regulatory

    def _resolve_redirect(self, url: str) -> Tuple[bool, str, Optional[str]]:
        """
        Follow redirects to get the final URL.

        Returns:
            Tuple of (success, final_url, error).
        """
        try:
            response = self.session.head(
                url,
                allow_redirects=True,
                timeout=REQUEST_TIMEOUT,
            )
            return True, response.url, None
        except requests.exceptions.Timeout:
            return False, url, "Request timed out"
        except requests.exceptions.RequestException as e:
            return False, url, str(e)

    def _fetch_and_extract_links(self, url: str) -> Tuple[bool, List[str], Optional[str]]:
        """
        Fetch a page and extract all links.

        Returns:
            Tuple of (success, links, error).
        """
        try:
            response = self.session.get(
                url,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
            )
            response.raise_for_status()

            links = self._extract_links_from_html(response.text, response.url)
            return True, links, None

        except requests.exceptions.Timeout:
            return False, [], "Request timed out"
        except requests.exceptions.HTTPError as e:
            return False, [], f"HTTP {e.response.status_code}"
        except requests.exceptions.RequestException as e:
            return False, [], str(e)

    def resolve(self, url: str) -> ResolveResult:
        """
        Resolve a URL to its actual document location.

        Args:
            url: URL to resolve.

        Returns:
            ResolveResult with resolution status and details.
        """
        if not url:
            return ResolveResult(
                success=False,
                original_url=url or "",
                error="No URL provided",
            )

        url = url.strip()
        domain = self._get_domain(url)

        # Check if it's already a direct document URL
        if self._is_trusted_domain(url):
            doc_type = self._detect_document_type(url)
            is_paid = self._is_paid_domain(url)

            return ResolveResult(
                success=not is_paid,
                original_url=url,
                resolved_url=url,
                document_type=doc_type,
                domain=domain,
                is_paid=is_paid,
                error="Paid domain - requires purchase" if is_paid else None,
            )

        # Check if it's a short URL or redirect
        if any(short in (domain or "") for short in ["t.co", "bit.ly", "lnkd.in", "ow.ly", "buff.ly", "tinyurl.com"]):
            success, final_url, error = self._resolve_redirect(url)
            if success:
                # Recursively resolve the final URL
                return self.resolve(final_url)
            return ResolveResult(
                success=False,
                original_url=url,
                error=error or "Could not resolve redirect",
            )

        # Check if it's a social media URL
        if self._is_social_url(url):
            # Try to fetch the page and extract links
            success, links, error = self._fetch_and_extract_links(url)

            if not success:
                return ResolveResult(
                    success=False,
                    original_url=url,
                    needs_manual=True,
                    error=error or "Could not access social media page",
                )

            # Find regulatory links
            regulatory_links = self._find_regulatory_links(links)

            if regulatory_links:
                # Found regulatory link(s)
                best_link = regulatory_links[0]

                # Prefer PDF links
                for link in regulatory_links:
                    if link.lower().endswith(".pdf"):
                        best_link = link
                        break

                doc_type = self._detect_document_type(best_link)
                is_paid = self._is_paid_domain(best_link)

                return ResolveResult(
                    success=not is_paid,
                    original_url=url,
                    resolved_url=best_link,
                    document_type=doc_type,
                    domain=self._get_domain(best_link),
                    is_paid=is_paid,
                    all_links_found=regulatory_links,
                    error="Paid domain - requires purchase" if is_paid else None,
                )
            else:
                # No regulatory links found
                return ResolveResult(
                    success=False,
                    original_url=url,
                    needs_manual=True,
                    all_links_found=links[:10],  # Include some found links for reference
                    error="No regulatory domain links found in page",
                )

        # Unknown URL type - try to detect document type
        doc_type = self._detect_document_type(url)

        return ResolveResult(
            success=True,
            original_url=url,
            resolved_url=url,
            document_type=doc_type,
            domain=domain,
        )

    def resolve_batch(self, urls: List[str]) -> List[ResolveResult]:
        """
        Resolve multiple URLs.

        Args:
            urls: List of URLs to resolve.

        Returns:
            List of ResolveResult objects.
        """
        results = []
        for url in urls:
            result = self.resolve(url)
            results.append(result)
            logger.debug(
                f"Resolved {url} -> {result.resolved_url or 'FAILED'}"
                f" ({result.error or 'OK'})"
            )
        return results

    def is_downloadable(self, url: str) -> Tuple[bool, str]:
        """
        Quick check if a URL is likely downloadable.

        Args:
            url: URL to check.

        Returns:
            Tuple of (is_downloadable, reason).
        """
        if not url:
            return False, "No URL"

        domain = self._get_domain(url)

        if self._is_paid_domain(url):
            return False, f"Paid domain ({domain})"

        if self._is_social_url(url):
            return False, "Social media URL - needs resolution"

        if self._is_trusted_domain(url):
            return True, "Trusted regulatory domain"

        return True, "Unknown domain - may work"


# Global resolver instance
url_resolver = URLResolver()
