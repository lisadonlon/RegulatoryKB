"""Tests for version extraction and checking."""

from regkb.version_tracker import (
    VersionInfo,
    check_document_version,
    extract_version_from_title,
    get_version_summary,
    normalize_doc_identifier,
)


class TestExtractVersionFromTitle:
    def test_rev_pattern(self):
        version, year = extract_version_from_title("MDCG 2019-11 Rev. 1")
        assert version == "Rev. 1"

    def test_v_pattern(self):
        version, year = extract_version_from_title("Document v2.0")
        assert version == "v2.0"

    def test_edition_pattern(self):
        version, year = extract_version_from_title("Standard Ed. 3")
        assert version == "Ed. 3"

    def test_year_extraction(self):
        version, year = extract_version_from_title("ISO 13485:2016")
        assert year == "2016"

    def test_combined_version_and_year(self):
        version, year = extract_version_from_title("MDCG 2020-1 Rev. 1")
        assert version == "Rev. 1"
        assert year == "2020"

    def test_no_version_returns_none(self):
        version, year = extract_version_from_title("Plain Document Title")
        assert version is None
        assert year is None


class TestNormalizeDocIdentifier:
    def test_mdcg_refs(self):
        result = normalize_doc_identifier("MDCG 2019-11 Software Guidance")
        assert result == "MDCG 2019-11"

    def test_iso_standards(self):
        result = normalize_doc_identifier("ISO 13485 Quality Management")
        assert result == "ISO 13485"

    def test_iec_standards(self):
        result = normalize_doc_identifier("IEC 62304 Software Lifecycle")
        assert result == "IEC 62304"

    def test_mdr(self):
        result = normalize_doc_identifier("MDR 2017/745 Medical Device Regulation")
        assert result == "MDR 2017/745"

    def test_ivdr(self):
        result = normalize_doc_identifier("IVDR 2017/746")
        assert result == "IVDR 2017/746"

    def test_cfr(self):
        result = normalize_doc_identifier("21 CFR Part 820")
        assert result == "21 CFR Part 820"

    def test_uk_mdr(self):
        result = normalize_doc_identifier("UK MDR 2002 Amendments")
        assert result == "UK MDR 2002"

    def test_unrecognized_returns_none(self):
        result = normalize_doc_identifier("Random Document Title")
        assert result is None


class TestCheckDocumentVersion:
    def test_known_current_doc(self):
        doc = {
            "id": 1,
            "title": "ISO 14971 Application of Risk Management",
            "jurisdiction": "ISO",
            "version": "2019",
        }
        info = check_document_version(doc)
        assert info.status == "current"

    def test_known_outdated_doc(self):
        doc = {
            "id": 2,
            "title": "MDCG 2019-11 Software Qualification Rev. 0",
            "jurisdiction": "EU",
            "version": "Rev. 0",
        }
        info = check_document_version(doc)
        # Rev. 0 is older than Rev. 1 (the known latest)
        assert info.status == "outdated"

    def test_unknown_doc(self):
        doc = {
            "id": 3,
            "title": "Some Unknown Document",
            "jurisdiction": "EU",
            "version": None,
        }
        info = check_document_version(doc)
        assert info.status == "unknown"


class TestGetVersionSummary:
    def test_correct_counts_by_status(self):
        results = [
            VersionInfo(
                doc_id=1,
                title="Doc A",
                jurisdiction="EU",
                current_version="1.0",
                latest_version="1.0",
                current_date=None,
                latest_date=None,
                is_current=True,
                status="current",
            ),
            VersionInfo(
                doc_id=2,
                title="Doc B",
                jurisdiction="EU",
                current_version="1.0",
                latest_version="2.0",
                current_date=None,
                latest_date=None,
                is_current=False,
                status="outdated",
            ),
            VersionInfo(
                doc_id=3,
                title="Doc C",
                jurisdiction="FDA",
                current_version=None,
                latest_version=None,
                current_date=None,
                latest_date=None,
                is_current=True,
                status="unknown",
            ),
        ]
        summary = get_version_summary(results)
        assert summary["total"] == 3
        assert summary["current"] == 1
        assert summary["outdated"] == 1
        assert summary["unknown"] == 1

    def test_by_jurisdiction(self):
        results = [
            VersionInfo(
                doc_id=1,
                title="A",
                jurisdiction="EU",
                current_version=None,
                latest_version=None,
                current_date=None,
                latest_date=None,
                is_current=True,
                status="current",
            ),
            VersionInfo(
                doc_id=2,
                title="B",
                jurisdiction="FDA",
                current_version=None,
                latest_version=None,
                current_date=None,
                latest_date=None,
                is_current=True,
                status="unknown",
            ),
        ]
        summary = get_version_summary(results)
        assert summary["by_jurisdiction"]["EU"]["total"] == 1
        assert summary["by_jurisdiction"]["EU"]["current"] == 1
        assert summary["by_jurisdiction"]["FDA"]["total"] == 1
        assert summary["by_jurisdiction"]["FDA"]["unknown"] == 1
