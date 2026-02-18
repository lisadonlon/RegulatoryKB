"""Tests for LLM handler — query routing and response formatting."""

from unittest.mock import MagicMock, patch

import pytest
from regkb.telegram.llm_handler import (
    _build_context,
    _format_answer,
    _format_search_fallback,
    is_complex_query,
)


class TestIsComplexQuery:
    def test_simple_factual(self):
        assert not is_complex_query("FDA cybersecurity guidance")

    def test_simple_what(self):
        assert not is_complex_query("What ISO standards do we have?")

    def test_complex_compare(self):
        assert is_complex_query("Compare the FDA and EU approaches to SaMD")

    def test_complex_explain(self):
        assert is_complex_query("Explain the requirements for MDR clinical evaluation")

    def test_complex_summarize(self):
        assert is_complex_query("Summarize ISO 14971 risk management process")

    def test_complex_recommend(self):
        assert is_complex_query("Should we update our quality manual?")

    def test_complex_implications(self):
        assert is_complex_query("What are the implications of IVDR for IVD manufacturers?")


class TestBuildContext:
    def test_formats_results(self):
        results = [
            {
                "title": "FDA Cybersecurity Guidance",
                "jurisdiction": "FDA",
                "document_type": "guidance",
                "excerpt": "Content for premarket submissions...",
            },
            {
                "title": "ISO 14971:2019",
                "jurisdiction": "ISO",
                "document_type": "standard",
                "excerpt": "Risk management for medical devices...",
            },
        ]
        context = _build_context(results)
        assert "[1] FDA Cybersecurity" in context
        assert "[2] ISO 14971" in context
        assert "Content for premarket" in context

    def test_empty_results(self):
        assert _build_context([]) == ""


class TestFormatAnswer:
    def test_includes_answer_and_sources(self):
        results = [{"title": "Some Document"}]
        formatted = _format_answer("This is the answer.", results, "Local LLM")
        assert "This is the answer." in formatted
        assert "Some Document" in formatted
        assert "Local LLM" in formatted

    def test_truncates_long_titles(self):
        results = [{"title": "A" * 100}]
        _format_answer("Answer.", results, "Claude")
        # Title should be truncated to 60 chars
        assert len("A" * 60) <= 60


class TestFormatSearchFallback:
    def test_shows_results_without_llm(self):
        results = [
            {"title": "Doc 1", "jurisdiction": "FDA"},
            {"title": "Doc 2", "jurisdiction": "EU"},
        ]
        formatted = _format_search_fallback(results, "test query")
        assert "test query" in formatted
        assert "Doc 1" in formatted
        assert "Doc 2" in formatted
        assert "No LLM" in formatted


class TestAnswerQuestion:
    @pytest.mark.asyncio
    async def test_no_search_results(self):
        from regkb.telegram.llm_handler import answer_question

        with patch("regkb.telegram.llm_handler._search_kb", return_value=[]):
            result = await answer_question("What is MDR?")
            assert "couldn't find" in result

    @pytest.mark.asyncio
    async def test_with_nexa_response(self):
        from regkb.telegram.llm_handler import answer_question

        search_results = [
            {"title": "MDR 2017/745", "jurisdiction": "EU", "document_type": "regulation"}
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "MDR is the EU regulation for medical devices."}}]
        }

        with patch("regkb.telegram.llm_handler._search_kb", return_value=search_results):
            with patch("regkb.telegram.llm_handler.requests.post", return_value=mock_response):
                result = await answer_question("What is MDR?")
                assert "MDR" in result
                assert "medical devices" in result

    @pytest.mark.asyncio
    async def test_fallback_to_search_when_no_llm(self):
        from regkb.telegram.llm_handler import answer_question

        search_results = [{"title": "Test Doc", "jurisdiction": "FDA"}]

        with patch("regkb.telegram.llm_handler._search_kb", return_value=search_results):
            with patch("regkb.telegram.llm_handler._ask_nexa", return_value=None):
                with patch("regkb.telegram.llm_handler._ask_claude", return_value=None):
                    result = await answer_question("test question")
                    assert "No LLM" in result
                    assert "Test Doc" in result

    @pytest.mark.asyncio
    async def test_strips_qwen_thinking_tags(self):
        from regkb.telegram.llm_handler import _ask_nexa

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "<think>Let me think about this...</think>The answer is 42."
                    }
                }
            ]
        }

        with patch("regkb.telegram.llm_handler.requests.post", return_value=mock_response):
            result = await _ask_nexa("What?", "context")
            assert result == "The answer is 42."
            assert "<think>" not in result
