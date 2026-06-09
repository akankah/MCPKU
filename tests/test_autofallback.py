"""Pytest tests for memory MCP CRUD operations (converted from script)."""

import json
import sys
import pytest
sys.path.insert(0, r"E:\MCPKU")

from mcp_memory import (
    search_nodes,
    read_graph,
    open_nodes,
    create_entities,
    add_observations,
    delete_entities,
    delete_observations,
)


@pytest.mark.asyncio
async def test_read_graph_returns_entities():
    result = json.loads(await read_graph())
    assert "entities" in result
    assert "relations" in result
    assert isinstance(result["entities"], list)
    assert isinstance(result["relations"], list)


@pytest.mark.asyncio
async def test_search_nodes_autofallback():
    result = json.loads(await search_nodes("autofallback"))
    assert "entities" in result
    assert isinstance(result["entities"], list)


@pytest.mark.asyncio
async def test_search_nodes_by_observation():
    result = json.loads(await search_nodes("penalaran kode"))
    assert "entities" in result
    assert isinstance(result["entities"], list)


@pytest.mark.asyncio
async def test_open_nodes_exact_entity():
    result = json.loads(await open_nodes(["AutofallbackRule"]))
    assert "entities" in result
    assert len(result["entities"]) > 0
    entity = result["entities"][0]
    assert entity["name"] == "AutofallbackRule"
    assert "observations" in entity


@pytest.mark.asyncio
async def test_add_and_verify_observation():
    test_obs = "[TEST] Verify write path works correctly."
    await add_observations([{
        "entityName": "AutofallbackRule",
        "contents": [test_obs]
    }])
    check = json.loads(await open_nodes(["AutofallbackRule"]))
    obs_list = check["entities"][0]["observations"]
    assert any(test_obs in o for o in obs_list)


@pytest.mark.asyncio
async def test_create_and_delete_transient_entity():
    tmp_name = "_TestEntity_TRANSIENT"
    try:
        await create_entities([{
            "name": tmp_name, "entityType": "test",
            "observations": ["will be deleted"]
        }])
        check = json.loads(await read_graph())
        assert any(e["name"] == tmp_name for e in check["entities"])
    finally:
        await delete_entities([tmp_name])
    check = json.loads(await read_graph())
    assert not any(e["name"] == tmp_name for e in check["entities"])


@pytest.mark.asyncio
async def test_cleanup_test_observation():
    test_obs = "[TEST] Verify write path works correctly."
    await delete_observations([{
        "entityName": "AutofallbackRule",
        "observations": [test_obs]
    }])
    final = json.loads(await open_nodes(["AutofallbackRule"]))
    remaining = [o for o in final["entities"][0]["observations"] if "[TEST]" in o]
    assert len(remaining) == 0
