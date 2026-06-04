import os, json, shutil
from mcp.server.fastmcp import FastMCP

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_JSONL = os.environ.get("MEMORY_FILE_PATH", os.path.join(BASE_DIR, "memory.jsonl"))
MEMORY_JSON = os.path.join(BASE_DIR, "memory.json")

mcp = FastMCP("memory", instructions="""
Knowledge graph memory with entities, relations, and observations.
Data is persisted in JSONL format. Use create_entities/add_observations
to store information, search_nodes/open_nodes to retrieve it.
""")

migrated = False

def _ensure_jsonl():
    global migrated
    if migrated: return
    if os.path.exists(MEMORY_JSON) and not os.path.exists(MEMORY_JSONL):
        try:
            with open(MEMORY_JSON, "r", encoding="utf-8") as f:
                old = json.load(f)
            lines = []
            for key, val in old.items():
                if isinstance(val, str):
                    lines.append(json.dumps({
                        "type": "entity", "name": key.replace(" ", "_"),
                        "entityType": "fact", "observations": [val]
                    }, ensure_ascii=False))
            if lines:
                with open(MEMORY_JSONL, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))
            os.rename(MEMORY_JSON, MEMORY_JSON + ".bak")
        except Exception: pass
    migrated = True

def _load() -> dict:
    _ensure_jsonl()
    graph = {"entities": [], "relations": []}
    if not os.path.exists(MEMORY_JSONL): return graph
    try:
        with open(MEMORY_JSONL, "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line: continue
                item = json.loads(line)
                if item.get("type") == "entity":
                    graph["entities"].append({
                        "name": item["name"],
                        "entityType": item.get("entityType", "unknown"),
                        "observations": item.get("observations", [])
                    })
                elif item.get("type") == "relation":
                    graph["relations"].append({
                        "from": item["from"], "to": item["to"],
                        "relationType": item["relationType"]
                    })
    except Exception: pass
    return graph

def _save(graph: dict):
    _ensure_jsonl()
    lines = []
    for e in graph.get("entities", []):
        lines.append(json.dumps({"type": "entity", "name": e["name"], "entityType": e["entityType"], "observations": e.get("observations", [])}, ensure_ascii=False))
    for r in graph.get("relations", []):
        lines.append(json.dumps({"type": "relation", "from": r["from"], "to": r["to"], "relationType": r["relationType"]}, ensure_ascii=False))
    os.makedirs(os.path.dirname(MEMORY_JSONL) or ".", exist_ok=True)
    with open(MEMORY_JSONL, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

@mcp.tool(
    name="create_entities",
    description="Create multiple new entities in the knowledge graph. Skips entities with existing names."
)
async def create_entities(entities: list) -> str:
    graph = _load()
    existing_names = {e["name"] for e in graph["entities"]}
    added = []
    for e in entities:
        if e.get("name") not in existing_names:
            graph["entities"].append({
                "name": e["name"],
                "entityType": e.get("entityType", "unknown"),
                "observations": e.get("observations", [])
            })
            added.append(e)
            existing_names.add(e["name"])
    _save(graph)
    return json.dumps(added, indent=2, ensure_ascii=False)

@mcp.tool(
    name="create_relations",
    description="Create multiple new relations between entities. Relations should be in active voice."
)
async def create_relations(relations: list) -> str:
    graph = _load()
    existing = {(r["from"], r["to"], r["relationType"]) for r in graph["relations"]}
    added = []
    for r in relations:
        key = (r.get("from", ""), r.get("to", ""), r.get("relationType", ""))
        if key not in existing:
            graph["relations"].append({"from": r["from"], "to": r["to"], "relationType": r["relationType"]})
            added.append(r)
            existing.add(key)
    _save(graph)
    return json.dumps(added, indent=2, ensure_ascii=False)

@mcp.tool(
    name="add_observations",
    description="Add new observations to existing entities. Fails if entity doesn't exist."
)
async def add_observations(observations: list) -> str:
    graph = _load()
    entity_map = {e["name"]: e for e in graph["entities"]}
    results = []
    for o in observations:
        ename = o.get("entityName", "")
        if ename not in entity_map:
            return f"(error: entity '{ename}' not found)"
        entity = entity_map[ename]
        existing_set = set(entity["observations"])
        added = [c for c in o.get("contents", []) if c not in existing_set]
        entity["observations"].extend(added)
        results.append({"entityName": ename, "addedObservations": added})
    _save(graph)
    return json.dumps(results, indent=2, ensure_ascii=False)

@mcp.tool(
    name="delete_entities",
    description="Delete multiple entities and their associated relations from the knowledge graph."
)
async def delete_entities(entity_names: list) -> str:
    graph = _load()
    names_set = set(entity_names)
    graph["entities"] = [e for e in graph["entities"] if e["name"] not in names_set]
    graph["relations"] = [r for r in graph["relations"] if r["from"] not in names_set and r["to"] not in names_set]
    _save(graph)
    return "Entities deleted successfully"

@mcp.tool(
    name="delete_observations",
    description="Delete specific observations from entities in the knowledge graph."
)
async def delete_observations(deletions: list) -> str:
    graph = _load()
    entity_map = {e["name"]: e for e in graph["entities"]}
    for d in deletions:
        ename = d.get("entityName", "")
        if ename in entity_map:
            remove_set = set(d.get("observations", []))
            entity_map[ename]["observations"] = [o for o in entity_map[ename]["observations"] if o not in remove_set]
    _save(graph)
    return "Observations deleted successfully"

@mcp.tool(
    name="delete_relations",
    description="Delete multiple relations from the knowledge graph."
)
async def delete_relations(relations: list) -> str:
    graph = _load()
    to_remove = {(r["from"], r["to"], r["relationType"]) for r in relations}
    graph["relations"] = [r for r in graph["relations"] if (r["from"], r["to"], r["relationType"]) not in to_remove]
    _save(graph)
    return "Relations deleted successfully"

@mcp.tool(
    name="read_graph",
    description="Read the entire knowledge graph with all entities and relations."
)
async def read_graph() -> str:
    graph = _load()
    return json.dumps(graph, indent=2, ensure_ascii=False)

@mcp.tool(
    name="search_nodes",
    description="Search for nodes based on query. Matches names, types, and observation content."
)
async def search_nodes(query: str) -> str:
    graph = _load()
    q = query.lower()
    filtered = [e for e in graph["entities"]
        if q in e["name"].lower() or q in e["entityType"].lower()
        or any(q in o.lower() for o in e.get("observations", []))]
    names = {e["name"] for e in filtered}
    rels = [r for r in graph["relations"] if r["from"] in names or r["to"] in names]
    return json.dumps({"entities": filtered, "relations": rels}, indent=2, ensure_ascii=False)

@mcp.tool(
    name="open_nodes",
    description="Open specific nodes by their names. Returns requested entities and their relations."
)
async def open_nodes(names: list) -> str:
    graph = _load()
    names_set = set(names)
    filtered = [e for e in graph["entities"] if e["name"] in names_set]
    rels = [r for r in graph["relations"] if r["from"] in names_set or r["to"] in names_set]
    return json.dumps({"entities": filtered, "relations": rels}, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    mcp.run(transport="stdio")
