import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import tempfile
import os
import json
from pathlib import Path
from mcp_memory import _load, _save, MEMORY_JSONL


class TestMemoryGraph:
    @pytest.fixture
    def graph_file(self, monkeypatch):
        data = json.dumps({"entities": [], "relations": []})
        tmp = Path(tempfile.mktemp(suffix=".jsonl"))
        tmp.write_text(data + "\n", encoding="utf-8")
        monkeypatch.setattr("mcp_memory.MEMORY_JSONL", str(tmp))
        yield tmp
        os.unlink(str(tmp))

    def test_load_empty_graph(self, graph_file):
        graph = _load()
        assert "entities" in graph
        assert "relations" in graph
        assert graph["entities"] == []

    def test_save_and_reload(self, graph_file):
        graph = {"entities": [{"name": "test", "entityType": "test"}], "relations": []}
        _save(graph)
        loaded = _load()
        assert len(loaded["entities"]) == 1
        assert loaded["entities"][0]["name"] == "test"

    def test_save_with_observations(self, graph_file):
        graph = {
            "entities": [{"name": "foo", "entityType": "concept", "observations": ["obs1"]}],
            "relations": []
        }
        _save(graph)
        loaded = _load()
        assert "observations" in loaded["entities"][0]
