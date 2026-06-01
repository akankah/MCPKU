import sys
sys.path.insert(0, r"E:\MCPKU")

import pytest
from mcp_vector import _embed_fallback, _table_name


class TestEmbedFallback:
    def test_returns_list_of_lists(self):
        result = _embed_fallback(["hello world"])
        assert isinstance(result, list)
        assert isinstance(result[0], list)

    def test_deterministic(self):
        r1 = _embed_fallback(["test"])
        r2 = _embed_fallback(["test"])
        assert r1 == r2

    def test_different_inputs_different_embeddings(self):
        r1 = _embed_fallback(["hello"])
        r2 = _embed_fallback(["world"])
        assert r1 != r2

    def test_multiple_texts(self):
        result = _embed_fallback(["a", "b"])
        assert len(result) == 2

    def test_embedding_dimension(self):
        result = _embed_fallback(["test"])
        assert len(result[0]) > 0


class TestTableName:
    def test_sanitizes_name(self):
        assert _table_name("my-collection") == "vec_my_collection"

    def test_replaces_spaces(self):
        assert _table_name("my collection") == "vec_my_collection"

    def test_special_chars_replaced_with_underscore(self):
        result = _table_name("foo!@#bar")
        assert result.startswith("vec_foo")
        assert "_bar" in result

    def test_empty_string(self):
        result = _table_name("")
        assert result.startswith("vec_")
