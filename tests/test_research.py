"""Tests for mcp_research.py — pure function tests (no network)."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_research import (
    _cosine_similarity,
    _lexical_similarity,
    _extract_keywords,
    _detect_language,
    _try_parse_json,
)


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 2.0, 3.0]
        assert _cosine_similarity(v, v) == 1.0

    def test_orthogonal_vectors(self):
        v1 = [1.0, 0.0]
        v2 = [0.0, 1.0]
        assert _cosine_similarity(v1, v2) == 0.0

    def test_zero_vector(self):
        v1 = [1.0, 0.0]
        v2 = [0.0, 0.0]
        assert _cosine_similarity(v1, v2) == 0.0
        assert _cosine_similarity(v2, v1) == 0.0

    def test_partial_similarity(self):
        v1 = [1.0, 0.0]
        v2 = [1.0, 1.0]
        sim = _cosine_similarity(v1, v2)
        assert 0.5 < sim < 1.0


class TestLexicalSimilarity:
    def test_identical_texts(self):
        assert _lexical_similarity("foo bar baz", "foo bar baz") == 1.0

    def test_no_overlap(self):
        assert _lexical_similarity("foo bar", "baz qux") == 0.0

    def test_partial_overlap(self):
        sim = _lexical_similarity("foo bar baz", "foo bar qux")
        # 2 common / 4 union = 0.5
        assert sim == 0.5

    def test_short_words_ignored(self):
        assert _lexical_similarity("a an the", "foo bar") == 0.0

    def test_empty_input(self):
        assert _lexical_similarity("", "foo") == 0.0
        assert _lexical_similarity("foo", "") == 0.0
        assert _lexical_similarity("", "") == 0.0


class TestExtractKeywords:
    def test_returns_first_words(self):
        result = _extract_keywords("quick brown fox jumps over lazy dog", max_words=4)
        # "over" is a stop word, so it's filtered: quick brown fox jumps lazy dog
        assert result == "quick brown fox jumps"
        assert len(result.split()) == 4

    def test_respects_max_words(self):
        result = _extract_keywords("a b c d e f g h i j", max_words=3)
        assert len(result.split()) <= 3

    def test_removes_noise_chars(self):
        result = _extract_keywords("hello, world! test...", max_words=3)
        assert "hello" in result

    def test_empty_string(self):
        assert _extract_keywords("") == ""


class TestDetectLanguage:
    def test_detects_python(self):
        assert _detect_language("python") == "python"

    def test_detects_by_substring(self):
        assert _detect_language("nodejs") == "javascript"

    def test_detects_js(self):
        assert _detect_language("javascript") == "javascript"

    def test_detects_rust(self):
        assert _detect_language("rust") == "rust"

    def test_detects_python_via_error(self):
        assert _detect_language("modulenotfounderror") == "python"

    def test_detects_cargo(self):
        assert _detect_language("cargo build") == "rust"

    def test_unknown_returns_general(self):
        assert _detect_language("brainfuck") == "general"

    def test_empty_returns_general(self):
        assert _detect_language("") == "general"


class TestTryParseJson:
    def test_valid_json(self):
        result = _try_parse_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_invalid_json(self):
        assert _try_parse_json("{broken") is None

    def test_single_quotes_not_valid_json(self):
        # json.loads requires double quotes
        assert _try_parse_json("{'key': 'value'}") is None

    def test_double_quotes_works(self):
        result = _try_parse_json('{"a": {"b": [1, 2]}}')
        assert result == {"a": {"b": [1, 2]}}

    def test_empty_string(self):
        assert _try_parse_json("") is None
