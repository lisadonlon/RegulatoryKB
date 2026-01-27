"""Tests for gap analysis pure matching logic."""

from regkb.gap_analysis import (
    MatchResult,
    calculate_match_score,
    extract_doc_identifiers,
    find_best_match,
    get_gap_summary,
    normalize_title,
)


class TestNormalizeTitle:
    def test_parentheticals_removed(self):
        result = normalize_title("ISO 13485 (Medical Devices)")
        assert "medical devices" not in result
        assert "iso" in result

    def test_version_suffixes_stripped(self):
        result = normalize_title("Document v2.0 extra")
        assert "v2" not in result

    def test_special_chars_removed(self):
        result = normalize_title("ISO/IEC 62304:2006")
        assert ":" not in result
        assert "/" not in result

    def test_whitespace_collapsed(self):
        result = normalize_title("ISO   13485    Quality")
        assert "  " not in result


class TestExtractDocIdentifiers:
    def test_iso_numbers(self):
        ids = extract_doc_identifiers("ISO 13485 Quality Management")
        assert "iso13485" in ids

    def test_mdcg_refs(self):
        ids = extract_doc_identifiers("MDCG 2019-11 Software Guidance")
        assert "mdcg2019-11" in ids

    def test_cfr_refs(self):
        ids = extract_doc_identifiers("21 CFR Part 820")
        assert "cfr820" in ids

    def test_mdr_ivdr_mdd(self):
        ids = extract_doc_identifiers("MDR 2017/745")
        assert "mdr2017/745" in ids

    def test_celex(self):
        ids = extract_doc_identifiers("CELEX 2017R0745 document")
        assert any("celex" in i for i in ids)


class TestCalculateMatchScore:
    def test_identifier_match_gives_high_score(self):
        ref_doc = {"title": "ISO 13485 Quality Management", "jurisdiction": "ISO"}
        score = calculate_match_score(ref_doc, "ISO 13485:2016 QMS", "ISO")
        assert score >= 0.8

    def test_keyword_overlap(self):
        ref_doc = {"title": "Quality Management Systems", "jurisdiction": "ISO"}
        score = calculate_match_score(ref_doc, "Quality Management Requirements", "ISO")
        assert score > 0.0

    def test_jurisdiction_bonus(self):
        ref_doc = {"title": "Software Guidelines", "jurisdiction": "EU"}
        score_match = calculate_match_score(ref_doc, "Software Guidelines", "EU")
        score_no_match = calculate_match_score(ref_doc, "Software Guidelines", "FDA")
        assert score_match > score_no_match

    def test_capped_at_one(self):
        ref_doc = {
            "title": "ISO 13485 Quality Management",
            "description": "Quality management systems for medical devices",
            "jurisdiction": "ISO",
        }
        score = calculate_match_score(
            ref_doc, "ISO 13485 Quality Management Systems for Medical Devices", "ISO"
        )
        assert score <= 1.0


class TestFindBestMatch:
    def test_returns_best_match_above_threshold(self):
        ref_doc = {"title": "ISO 13485 Quality Management", "jurisdiction": "ISO"}
        kb_docs = [
            {"title": "ISO 13485:2016 Quality Management Systems", "jurisdiction": "ISO"},
            {"title": "Unrelated Document", "jurisdiction": "EU"},
        ]
        match, score = find_best_match(ref_doc, kb_docs)
        assert match is not None
        assert match["title"] == "ISO 13485:2016 Quality Management Systems"
        assert score >= 0.5

    def test_returns_none_below_threshold(self):
        ref_doc = {"title": "ISO 13485 Quality Management", "jurisdiction": "ISO"}
        kb_docs = [
            {"title": "Completely Unrelated Thing", "jurisdiction": "FDA"},
        ]
        match, score = find_best_match(ref_doc, kb_docs)
        assert match is None
        assert score == 0.0


class TestGetGapSummary:
    def test_correct_totals(self):
        results = {
            "EU": [
                MatchResult(
                    ref_id="1",
                    ref_title="Doc A",
                    ref_description="",
                    jurisdiction="EU",
                    category="cat",
                    mandatory=True,
                    matched=True,
                ),
                MatchResult(
                    ref_id="2",
                    ref_title="Doc B",
                    ref_description="",
                    jurisdiction="EU",
                    category="cat",
                    mandatory=True,
                    matched=False,
                ),
            ],
        }
        summary = get_gap_summary(results)
        assert summary["total_reference"] == 2
        assert summary["total_matched"] == 1
        assert summary["total_missing"] == 1
        assert summary["mandatory_missing"] == 1

    def test_by_jurisdiction_breakdown(self):
        results = {
            "EU": [
                MatchResult(
                    ref_id="1",
                    ref_title="A",
                    ref_description="",
                    jurisdiction="EU",
                    category="c",
                    mandatory=False,
                    matched=True,
                ),
            ],
            "FDA": [
                MatchResult(
                    ref_id="2",
                    ref_title="B",
                    ref_description="",
                    jurisdiction="FDA",
                    category="c",
                    mandatory=False,
                    matched=False,
                ),
            ],
        }
        summary = get_gap_summary(results)
        assert "EU" in summary["by_jurisdiction"]
        assert "FDA" in summary["by_jurisdiction"]
        assert summary["by_jurisdiction"]["EU"]["matched"] == 1
        assert summary["by_jurisdiction"]["FDA"]["missing"] == 1

    def test_coverage_percentages(self):
        results = {
            "EU": [
                MatchResult(
                    ref_id="1",
                    ref_title="A",
                    ref_description="",
                    jurisdiction="EU",
                    category="c",
                    mandatory=False,
                    matched=True,
                ),
                MatchResult(
                    ref_id="2",
                    ref_title="B",
                    ref_description="",
                    jurisdiction="EU",
                    category="c",
                    mandatory=False,
                    matched=False,
                ),
            ],
        }
        summary = get_gap_summary(results)
        assert summary["by_jurisdiction"]["EU"]["coverage"] == 50.0
        assert summary["overall_coverage"] == 50.0
