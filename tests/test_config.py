"""Tests for Config validation and normalization."""


class TestValidateDocumentType:
    def test_valid_type(self, fresh_config):
        valid, msg = fresh_config.validate_document_type("guidance")
        assert valid is True
        assert msg == ""

    def test_invalid_type(self, fresh_config):
        valid, msg = fresh_config.validate_document_type("nonsense")
        assert valid is False
        assert "Invalid document type" in msg

    def test_close_misspelling_suggests(self, fresh_config):
        valid, msg = fresh_config.validate_document_type("guidanc")
        assert valid is False
        assert "Did you mean" in msg

    def test_empty_string(self, fresh_config):
        valid, msg = fresh_config.validate_document_type("")
        assert valid is False
        assert "cannot be empty" in msg


class TestValidateJurisdiction:
    def test_valid_jurisdiction(self, fresh_config):
        valid, msg = fresh_config.validate_jurisdiction("EU")
        assert valid is True
        assert msg == ""

    def test_invalid_jurisdiction(self, fresh_config):
        valid, msg = fresh_config.validate_jurisdiction("zzzzz")
        assert valid is False
        assert "Invalid jurisdiction" in msg

    def test_close_match_suggests(self, fresh_config):
        valid, msg = fresh_config.validate_jurisdiction("Irelan")
        assert valid is False
        assert "Did you mean" in msg

    def test_empty_string(self, fresh_config):
        valid, msg = fresh_config.validate_jurisdiction("")
        assert valid is False
        assert "cannot be empty" in msg


class TestNormalizeDocumentType:
    def test_exact_match(self, fresh_config):
        assert fresh_config.normalize_document_type("guidance") == "guidance"

    def test_case_insensitive(self, fresh_config):
        assert fresh_config.normalize_document_type("GUIDANCE") == "guidance"

    def test_unknown_falls_to_other(self, fresh_config):
        assert fresh_config.normalize_document_type("unknown_type") == "other"


class TestNormalizeJurisdiction:
    def test_exact_match(self, fresh_config):
        assert fresh_config.normalize_jurisdiction("EU") == "EU"

    def test_case_insensitive(self, fresh_config):
        assert fresh_config.normalize_jurisdiction("eu") == "EU"

    def test_unknown_falls_to_other(self, fresh_config):
        assert fresh_config.normalize_jurisdiction("Mars") == "Other"


class TestGet:
    def test_top_level_key(self, fresh_config):
        result = fresh_config.get("document_types")
        assert isinstance(result, list)
        assert "guidance" in result

    def test_dot_notation_nested_key(self, fresh_config):
        result = fresh_config.get("search.default_limit")
        assert result == 10

    def test_missing_key_returns_default(self, fresh_config):
        result = fresh_config.get("nonexistent.key", "fallback")
        assert result == "fallback"


class TestMergeConfig:
    def test_deep_merge_dict_keys(self, fresh_config):
        fresh_config._merge_config({"search": {"custom_key": 42}})
        assert fresh_config.get("search.custom_key") == 42
        # Original keys preserved
        assert fresh_config.get("search.default_limit") == 10

    def test_overwrite_non_dict_keys(self, fresh_config):
        fresh_config._merge_config({"document_types": ["custom"]})
        assert fresh_config.get("document_types") == ["custom"]
