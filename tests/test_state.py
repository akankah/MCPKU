import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import os
import tempfile
from pathlib import Path

import pytest

from mcp_state import state_init, state_update, _get_state_file


@pytest.fixture(autouse=True)
def isolate_state_file(monkeypatch):
    """Point _get_state_file to a temp directory so tests don't collide."""
    tmpdir = Path(tempfile.mkdtemp())
    monkeypatch.chdir(tmpdir)
    yield
    import shutil
    shutil.rmtree(str(tmpdir), ignore_errors=True)


class TestGetStateFile:
    def test_returns_path_in_cwd(self, monkeypatch):
        monkeypatch.chdir(r"E:\MCPKU")
        path = _get_state_file()
        assert path.name == "workflow_state.jsonl"
        assert path.parent == Path(r"E:\MCPKU").resolve()

    def test_respects_cwd_param(self):
        path = _get_state_file(cwd=r"E:\MCPKU")
        assert path.parent == Path(r"E:\MCPKU").resolve()


class TestStateInit:
    @pytest.mark.asyncio
    async def test_init_creates_state_file(self):
        result = await state_init(workflow_id="wf-1", plan='{"tasks":[]}')
        assert "initialized" in result
        path = _get_state_file()
        assert path.exists()

    @pytest.mark.asyncio
    async def test_init_writes_one_line(self):
        await state_init(workflow_id="wf-2", plan='{"tasks":["a"]}')
        path = _get_state_file()
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 1

    @pytest.mark.asyncio
    async def test_init_line_is_valid_json(self):
        await state_init(workflow_id="wf-3", plan='{"x":1}')
        path = _get_state_file()
        entry = json.loads(path.read_text().strip())
        assert entry["type"] == "init"
        assert entry["workflow_id"] == "wf-3"
        assert json.loads(entry["plan"]) == {"x": 1}

    @pytest.mark.asyncio
    async def test_init_overwrites_previous_file(self):
        await state_init("wf-a", "plan1")
        await state_init("wf-b", "plan2")
        path = _get_state_file()
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["workflow_id"] == "wf-b"


class TestStateUpdate:
    @pytest.mark.asyncio
    async def test_update_appends_to_existing(self):
        await state_init("wf-u", "{}")
        result = await state_update(workflow_id="wf-u", step_id="s1", status="completed")
        assert "updated" in result
        path = _get_state_file()
        lines = [json.loads(l) for l in path.read_text().strip().split("\n")]
        assert len(lines) == 2
        assert lines[1]["step_id"] == "s1"
        assert lines[1]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_update_creates_file_if_not_exists(self):
        result = await state_update("wf-fresh", "s1", "in_progress")
        assert "updated" in result
        path = _get_state_file()
        assert path.exists()

    @pytest.mark.asyncio
    async def test_update_with_error_info(self):
        await state_init("wf-err", "{}")
        await state_update("wf-err", "s1", "failed", error_info='{"msg":"timeout"}')
        path = _get_state_file()
        lines = path.read_text().strip().split("\n")
        entry = json.loads(lines[1])
        assert entry["status"] == "failed"
        assert entry["error_info"] == '{"msg":"timeout"}'

    @pytest.mark.asyncio
    async def test_update_with_verification(self):
        await state_init("wf-ver", "{}")
        await state_update("wf-ver", "s1", "completed", verification='{"tests":5}')
        path = _get_state_file()
        lines = path.read_text().strip().split("\n")
        entry = json.loads(lines[1])
        assert entry["status"] == "completed"
        assert entry["verification"] == '{"tests":5}'

    @pytest.mark.asyncio
    async def test_update_increments_attempt(self):
        await state_init("wf-att", "{}")
        await state_update("wf-att", "s1", "failed", attempt=3)
        path = _get_state_file()
        lines = path.read_text().strip().split("\n")
        entry = json.loads(lines[1])
        assert entry["attempt"] == 3

    @pytest.mark.asyncio
    async def test_update_all_valid_statuses(self):
        await state_init("wf-st", "{}")
        for status in ("pending", "in_progress", "completed", "failed", "rolled_back"):
            await state_update("wf-st", "s1", status)
        path = _get_state_file()
        lines = [json.loads(l) for l in path.read_text().strip().split("\n")]
        statuses = [l["status"] for l in lines[1:]]
        assert statuses == ["pending", "in_progress", "completed", "failed", "rolled_back"]

    @pytest.mark.asyncio
    async def test_update_timestamp_is_isoformat(self):
        from datetime import datetime
        await state_init("wf-ts", "{}")
        await state_update("wf-ts", "s1", "in_progress")
        path = _get_state_file()
        lines = path.read_text().strip().split("\n")
        entry = json.loads(lines[1])
        datetime.fromisoformat(entry["timestamp"])
