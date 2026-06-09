import os, json, re, hashlib, struct
from urllib.parse import urlparse
from typing import Any, Optional

import numpy as np
from mcp.server.fastmcp import FastMCP
from mcp_cache import cache_get, cache_set

DATABASE_URL = os.environ.get("DATABASE_URL", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
EMBEDDING_MODEL = os.environ.get("VECTOR_EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIM = int(os.environ.get("VECTOR_EMBEDDING_DIM", "1536"))

mcp = FastMCP("postgres-vector", instructions="""
PostgreSQL vector store with pgvector extension.
Semantic search via OpenAI embeddings (or token-hash fallback).
Set DATABASE_URL and OPENAI_API_KEY environment variables.
""")

_conn = None

def _get_conn() -> Any:
    global _conn
    if _conn is None:
        import psycopg2
        cs = DATABASE_URL
        if not cs:
            raise ValueError("DATABASE_URL not configured")
        _conn = psycopg2.connect(cs)
        _conn.autocommit = True
    return _conn

def _ensure_extension() -> None:
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
    cur.close()

def _table_name(collection: str) -> str:
    safe = re.sub(r'[^a-zA-Z0-9_]', '_', collection.lower().strip())
    if not safe or safe[0].isdigit():
        safe = 'c_' + safe
    return f"vec_{safe}"

def _embed(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    if not OPENAI_API_KEY:
        return _embed_fallback(texts)

    # Check Redis cache for each text
    results = [None] * len(texts)
    uncached = []

    for i, text in enumerate(texts):
        ck = "mcp:vec:embed:" + hashlib.sha256(text.encode()).hexdigest()[:32]
        cached = cache_get(ck)
        if cached is not None:
            results[i] = json.loads(cached)
        else:
            uncached.append((i, text))

    # Compute remaining via OpenAI
    if uncached:
        indices, need_texts = zip(*uncached)
        embeddings = _embed_openai(list(need_texts))
        for idx, emb in zip(indices, embeddings):
            results[idx] = emb
            ck = "mcp:vec:embed:" + hashlib.sha256(texts[idx].encode()).hexdigest()[:32]
            cache_set(ck, json.dumps(emb), ttl=86400)  # 24h TTL

    return results

def _embed_openai(texts: list[str]) -> list[list[float]]:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    r = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [d.embedding for d in r.data]

def _embed_fallback(texts: list[str]) -> list[list[float]]:
    results = []
    for t in texts:
        h = hashlib.sha256(t.encode()).digest()
        vec = [struct.unpack('f', h[i:i+4])[0] for i in range(0, min(64, len(h)-3), 4)]
        vec = vec * (EMBEDDING_DIM // len(vec) + 1)
        vec = vec[:EMBEDDING_DIM]
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = (np.array(vec) / norm).tolist()
        results.append(vec)
    return results

def _ok(data: dict = None) -> str:
    return json.dumps({"status": "ok", **({} if data is None else data)})

def _err(msg: str) -> str:
    return json.dumps({"status": "error", "message": msg})

@mcp.tool(
    name="create_collection",
    description="Create a vector collection (table) with specified dimension. Default dimension=1536 for text-embedding-3-small."
)
async def create_collection(name: str, dimension: int = None) -> str:
    dim = dimension or EMBEDDING_DIM
    try:
        _ensure_extension()
        tbl = _table_name(name)
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {tbl} (
                id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                metadata JSONB DEFAULT '{{}}',
                embedding vector({dim}),
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute(f"CREATE INDEX IF NOT EXISTS {tbl}_idx ON {tbl} USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)")
        cur.close()
        return _ok({"collection": name, "table": tbl, "dimension": dim})
    except Exception as e:
        return _err(str(e))

@mcp.tool(
    name="add_documents",
    description="Add documents to a vector collection. Each doc: {id, text, metadata?}. Auto-embeds text."
)
async def add_documents(collection: str, documents: list) -> str:
    if not documents:
        return _err("empty documents list")
    try:
        _ensure_extension()
        tbl = _table_name(collection)
        texts = [d.get("text", "") for d in documents]
        embeddings = _embed(texts)
        conn = _get_conn()
        cur = conn.cursor()
        added = 0
        for doc, emb in zip(documents, embeddings):
            doc_id = doc.get("id", hashlib.md5(doc.get("text", "").encode()).hexdigest()[:16])
            meta = json.dumps(doc.get("metadata", {}))
            emb_str = "[" + ",".join(str(v) for v in emb) + "]"
            cur.execute(f"""
                INSERT INTO {tbl} (id, text, metadata, embedding)
                VALUES (%s, %s, %s::jsonb, %s::vector)
                ON CONFLICT (id) DO UPDATE SET text=EXCLUDED.text, metadata=EXCLUDED.metadata, embedding=EXCLUDED.embedding
            """, (doc_id, doc.get("text", ""), meta, emb_str))
            added += 1
        cur.close()
        return _ok({"collection": collection, "added": added})
    except Exception as e:
        return _err(str(e))

@mcp.tool(
    name="search",
    description="Semantic search in a vector collection. Returns top_k most similar documents with scores."
)
async def search(collection: str, query: str, top_k: int = 5, min_score: float = 0.0) -> str:
    if not query.strip():
        return _err("empty query")
    try:
        _ensure_extension()
        tbl = _table_name(collection)
        qvec = _embed([query])[0]
        emb_str = "[" + ",".join(str(v) for v in qvec) + "]"
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(f"""
            SELECT id, text, metadata, 1 - (embedding <=> %s::vector) AS score
            FROM {tbl}
            WHERE 1 - (embedding <=> %s::vector) >= %s
            ORDER BY score DESC
            LIMIT %s
        """, (emb_str, emb_str, min_score, top_k))
        rows = cur.fetchall()
        cur.close()
        results = []
        for row in rows:
            results.append({
                "id": row[0], "text": row[1][:500],
                "metadata": row[2] if isinstance(row[2], dict) else json.loads(row[2]) if row[2] else {},
                "score": round(float(row[3]), 4)
            })
        return json.dumps({"results": results, "count": len(results)}, indent=2, ensure_ascii=False)
    except Exception as e:
        return _err(str(e))

@mcp.tool(
    name="delete_documents",
    description="Delete documents from a vector collection by IDs."
)
async def delete_documents(collection: str, ids: list) -> str:
    if not ids:
        return _err("empty ids list")
    try:
        tbl = _table_name(collection)
        conn = _get_conn()
        cur = conn.cursor()
        placeholders = ",".join("%s" for _ in ids)
        cur.execute(f"DELETE FROM {tbl} WHERE id IN ({placeholders})", ids)
        deleted = cur.rowcount
        cur.close()
        return _ok({"collection": collection, "deleted": deleted})
    except Exception as e:
        return _err(str(e))

@mcp.tool(
    name="list_collections",
    description="List all vector collections (tables with vec_ prefix)."
)
async def list_collections() -> str:
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_name LIKE 'vec_%' AND table_schema = 'public'
            ORDER BY table_name
        """)
        rows = cur.fetchall()
        cur.close()
        collections = []
        for row in rows:
            name = row[0][4:]
            cur2 = conn.cursor()
            cur2.execute(f"SELECT COUNT(*) FROM {row[0]}")
            count = cur2.fetchone()[0]
            cur2.close()
            collections.append({"name": name, "table": row[0], "documents": count})
        return json.dumps({"collections": collections, "count": len(collections)}, indent=2)
    except Exception as e:
        return _err(str(e))

@mcp.tool(
    name="collection_stats",
    description="Get statistics for a vector collection: document count, dimension, sample."
)
async def collection_stats(collection: str) -> str:
    try:
        tbl = _table_name(collection)
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(f"""
            SELECT
                COUNT(*) AS total,
                (SELECT embedding::text FROM {tbl} LIMIT 1) AS sample_vec
            FROM {tbl}
        """)
        row = cur.fetchone()
        total = row[0]
        dim = len(row[1].replace("{", "").replace("}", "").split(",")) if row[1] else 0
        cur.execute(f"SELECT id, text, created_at FROM {tbl} ORDER BY created_at DESC LIMIT 5")
        samples = [{"id": r[0], "text": r[1][:200], "created_at": str(r[2])} for r in cur.fetchall()]
        cur.close()
        return json.dumps({
            "collection": collection, "table": tbl,
            "total_documents": total, "dimension": dim,
            "recent_documents": samples
        }, indent=2)
    except Exception as e:
        return _err(str(e))

if __name__ == "__main__":
    if not DATABASE_URL:
        print("WARNING: DATABASE_URL not set. Tools will fail until configured.")
    mcp.run(transport="stdio")
