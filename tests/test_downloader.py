"""Tests for URL validation and filename sanitization."""

from unittest.mock import MagicMock, patch

import pytest
from regkb.downloader import DocumentDownloader


@pytest.fixture
def downloader(tmp_path):
    """Create DocumentDownloader with mocked config to avoid filesystem side effects."""
    mock_config = MagicMock()
    mock_config.archive_dir = tmp_path / "archive"
    with patch("regkb.downloader.config", mock_config):
        dl = DocumentDownloader()
    return dl


class TestValidateUrl:
    def test_valid_https(self, downloader):
        valid, error = downloader._validate_url("https://example.com/doc.pdf")
        assert valid is True
        assert error is None

    def test_valid_http(self, downloader):
        valid, error = downloader._validate_url("http://example.com/doc.pdf")
        assert valid is True
        assert error is None

    def test_empty_string(self, downloader):
        valid, error = downloader._validate_url("")
        assert valid is False
        assert "empty" in error.lower()

    def test_missing_scheme(self, downloader):
        valid, error = downloader._validate_url("example.com/doc.pdf")
        assert valid is False
        assert "scheme" in error.lower()

    def test_ftp_scheme(self, downloader):
        valid, error = downloader._validate_url("ftp://example.com/doc.pdf")
        assert valid is False
        assert "ftp" in error.lower()

    def test_missing_domain(self, downloader):
        valid, error = downloader._validate_url("https://")
        assert valid is False

    def test_no_tld(self, downloader):
        valid, error = downloader._validate_url("https://nodomain")
        assert valid is False
        assert "top-level domain" in error.lower()


class TestSanitizeFilename:
    def test_special_chars_replaced(self, downloader):
        result = downloader._sanitize_filename('file<>:"/\\|?*.pdf')
        assert "<" not in result
        assert ">" not in result
        assert "?" not in result

    def test_spaces_to_underscores(self, downloader):
        result = downloader._sanitize_filename("my document file.pdf")
        assert " " not in result
        assert "_" in result

    def test_strip_leading_trailing_dots(self, downloader):
        result = downloader._sanitize_filename("...filename...")
        assert not result.startswith(".")
        assert not result.endswith(".")

    def test_truncated_at_200(self, downloader):
        long_name = "a" * 300 + ".pdf"
        result = downloader._sanitize_filename(long_name)
        assert len(result) <= 200
