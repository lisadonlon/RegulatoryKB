"""Tests for diff statistics and generation."""

from regkb.diff import DiffStats, compute_diff_stats, generate_html_diff, generate_unified_diff


class TestComputeDiffStats:
    def test_identical_lines(self):
        lines = ["line 1\n", "line 2\n", "line 3\n"]
        stats = compute_diff_stats(lines, lines)
        assert stats.similarity == 1.0
        assert stats.unchanged == 3
        assert stats.added == 0
        assert stats.removed == 0

    def test_completely_different(self):
        lines1 = ["aaa\n", "bbb\n"]
        lines2 = ["xxx\n", "yyy\n", "zzz\n"]
        stats = compute_diff_stats(lines1, lines2)
        assert stats.similarity < 0.5
        # Everything changes: either replaced or inserted
        assert stats.changed > 0 or (stats.added > 0 and stats.removed > 0)

    def test_mixed_changes(self):
        lines1 = ["same\n", "old\n", "keep\n"]
        lines2 = ["same\n", "new\n", "keep\n", "extra\n"]
        stats = compute_diff_stats(lines1, lines2)
        assert stats.unchanged >= 2
        assert stats.similarity > 0.0
        assert stats.similarity < 1.0


class TestGenerateUnifiedDiff:
    def test_produces_unified_format(self):
        lines1 = ["hello\n", "world\n"]
        lines2 = ["hello\n", "earth\n"]
        result = generate_unified_diff(lines1, lines2, "doc1", "doc2")
        assert "---" in result
        assert "+++" in result
        assert "-world" in result
        assert "+earth" in result

    def test_empty_when_identical(self):
        lines = ["same\n"]
        result = generate_unified_diff(lines, lines, "a", "b")
        assert result == ""


class TestGenerateHtmlDiff:
    def test_returns_html_with_labels(self):
        lines1 = ["hello\n"]
        lines2 = ["world\n"]
        result = generate_html_diff(lines1, lines2, "Label A", "Label B")
        assert "<" in result  # Contains HTML tags
        assert "Label A" in result
        assert "Label B" in result


class TestDiffStatsSummary:
    def test_formatted_string(self):
        stats = DiffStats(added=5, removed=3, changed=2, unchanged=10, similarity=0.75)
        text = stats.summary()
        assert "75.0%" in text
        assert "Added: 5" in text
        assert "Removed: 3" in text
        assert "Changed: 2" in text
        assert "Unchanged: 10" in text
