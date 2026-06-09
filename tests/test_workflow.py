"""Tests for mcp_workflow.py — pure function tests (no workflow files)."""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, r"E:\MCPKU")

from mcp_workflow import _schema, _resolve_refs, _load_state, _append_event


class TestSchema:
    def test_returns_dict(self):
        s = _schema()
        assert isinstance(s, dict)
        assert "schema_version" in s
        assert "workflow" in s

    def test_has_required_keys(self):
        s = _schema()
        wf = s["workflow"]
        assert "id" in wf
        assert "name" in wf
        assert "steps" in wf


class TestResolveRefs:
    def test_resolves_query(self):
        result = _resolve_refs("Hello {query}", {}, "world")
        assert result == "Hello world"

    def test_resolves_outputs(self):
        context = {"outputs": {"step1": {"result": "42"}}}
        result = _resolve_refs("Answer: {outputs.step1.result}", context, "")
        assert result == "Answer: 42"

    def test_nested_outputs(self):
        context = {"outputs": {"step1": {"data": {"x": 1}}}}
        result = _resolve_refs("Data: {outputs.step1.data}", context, "")
        assert result == 'Data: {"x": 1}'

    def test_unknown_key_returns_placeholder(self):
        context = {"outputs": {}}
        result = _resolve_refs("{outputs.step1.missing}", context, "")
        assert result == "{outputs.step1.missing}"

    def test_no_placeholders(self):
        result = _resolve_refs("plain text", {}, "")
        assert result == "plain text"


class TestLoadState:
    def test_no_state_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _load_state(tmp)
            assert result == {}

    def test_loads_completed_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "workflow_state.jsonl"
            state_file.write_text(
                json.dumps({"step_id": "s1", "status": "completed"}) + "\n" +
                json.dumps({"step_id": "s2", "status": "failed"}) + "\n" +
                json.dumps({"step_id": "s3", "status": "completed"}) + "\n",
                encoding="utf-8"
            )
            result = _load_state(tmp)
            assert result == {"s1": "completed", "s2": "failed", "s3": "completed"}

    def test_ignores_unknown_statuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "workflow_state.jsonl"
            state_file.write_text(
                json.dumps({"step_id": "s1", "status": "running"}) + "\n",
                encoding="utf-8"
            )
            result = _load_state(tmp)
            assert result == {}

    def test_skips_empty_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "workflow_state.jsonl"
            state_file.write_text(
                "\n" +
                json.dumps({"step_id": "s1", "status": "completed"}) + "\n" +
                "\n",
                encoding="utf-8"
            )
            result = _load_state(tmp)
            assert result == {"s1": "completed"}


class TestAppendEvent:
    def test_creates_file_and_appends(self):
        with tempfile.TemporaryDirectory() as tmp:
            _append_event(tmp, {"event": "test", "data": 1})
            state_file = Path(tmp) / "workflow_state.jsonl"
            assert state_file.exists()
            lines = state_file.read_text(encoding="utf-8").strip().split("\n")
            assert len(lines) == 1
            entry = json.loads(lines[0])
            assert entry["event"] == "test"
            assert entry["data"] == 1
            assert "timestamp" in entry

    def test_appends_to_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            _append_event(tmp, {"event": "first"})
            _append_event(tmp, {"event": "second"})
            state_file = Path(tmp) / "workflow_state.jsonl"
            lines = state_file.read_text(encoding="utf-8").strip().split("\n")
            assert len(lines) == 2
