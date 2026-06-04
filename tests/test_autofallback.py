import asyncio
import json
import sys
sys.path.insert(0, r"E:\MCPKU")
from mcp_memory import search_nodes, read_graph, open_nodes, create_entities, add_observations, delete_entities

async def main():
    print("=" * 60)
    print("TEST 1: read_graph() — semua entities")
    print("=" * 60)
    result = json.loads(await read_graph())
    print(f"Total entities: {len(result['entities'])}")
    for e in result['entities']:
        print(f"  - {e['name']} (type={e['entityType']}, obs={len(e['observations'])})")
    print(f"Total relations: {len(result['relations'])}")

    print()
    print("=" * 60)
    print("TEST 2: search_nodes('autofallback') — query rule")
    print("=" * 60)
    result = json.loads(await search_nodes("autofallback"))
    print(f"Matched: {len(result['entities'])} entities")
    for e in result['entities']:
        print(f"  - {e['name']}")
        for o in e['observations']:
            print(f"      * {o[:90]}{'...' if len(o)>90 else ''}")

    print()
    print("=" * 60)
    print("TEST 3: search_nodes('penalaran kode') — search by observation content")
    print("=" * 60)
    result = json.loads(await search_nodes("penalaran kode"))
    print(f"Matched: {len(result['entities'])} entities")
    for e in result['entities']:
        print(f"  - {e['name']} (matched on: {[o for o in e['observations'] if 'penalaran' in o.lower()][0][:80]}...)")

    print()
    print("=" * 60)
    print("TEST 4: open_nodes(['AutofallbackRule']) — get exact entity")
    print("=" * 60)
    result = json.loads(await open_nodes(["AutofallbackRule"]))
    print(f"Entities: {len(result['entities'])}")
    for e in result['entities']:
        print(f"  Name: {e['name']}")
        print(f"  Type: {e['entityType']}")
        print(f"  Observations ({len(e['observations'])}):")
        for i, o in enumerate(e['observations'], 1):
            print(f"    {i}. {o[:100]}{'...' if len(o)>100 else ''}")

    print()
    print("=" * 60)
    print("TEST 5: add_observations() — tambah 1 observasi test")
    print("=" * 60)
    test_obs = "[2026-06-04] [TEST] Verify write path works correctly. Will be removed after test."
    result = await add_observations([{
        "entityName": "AutofallbackRule",
        "contents": [test_obs]
    }])
    print(f"Add result: {result}")
    # Verify
    check = json.loads(await open_nodes(["AutofallbackRule"]))
    has_test = any("[TEST]" in o for o in check['entities'][0]['observations'])
    print(f"Test obs present: {has_test}")

    print()
    print("=" * 60)
    print("TEST 6: delete_entities() — test create+delete transient entity")
    print("=" * 60)
    tmp = [{"name": "_TestEntity_TRANSIENT", "entityType": "test", "observations": ["will be deleted"]}]
    await create_entities(tmp)
    check = json.loads(await read_graph())
    has = any(e['name'] == "_TestEntity_TRANSIENT" for e in check['entities'])
    print(f"Created _TestEntity_TRANSIENT: {has}")
    await delete_entities(["_TestEntity_TRANSIENT"])
    check = json.loads(await read_graph())
    has_after = any(e['name'] == "_TestEntity_TRANSIENT" for e in check['entities'])
    print(f"After delete (should be False): {has_after}")

    # Cleanup test observation from AutofallbackRule
    from mcp_memory import delete_observations
    print()
    print("=" * 60)
    print("CLEANUP: remove test observation")
    print("=" * 60)
    await delete_observations([{
        "entityName": "AutofallbackRule",
        "observations": [test_obs]
    }])
    final = json.loads(await open_nodes(["AutofallbackRule"]))
    test_remaining = [o for o in final['entities'][0]['observations'] if "[TEST]" in o]
    print(f"Test obs remaining (should be 0): {len(test_remaining)}")
    print(f"Final obs count: {len(final['entities'][0]['observations'])}")

asyncio.run(main())
