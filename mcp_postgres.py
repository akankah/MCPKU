import os, json, re, threading
from typing import Optional
from urllib.parse import urlparse
from mcp_cache import cache_get, cache_set
from mcp.server.fastmcp import FastMCP

DATABASE_URL = os.environ.get("DATABASE_URL", "")
DB_POOL_MIN = int(os.environ.get("DB_POOL_MIN", "2"))
DB_POOL_MAX = int(os.environ.get("DB_POOL_MAX", "10"))
DB_HOST = "localhost"
if DATABASE_URL:
    parsed = urlparse(DATABASE_URL)
    DB_HOST = parsed.hostname or "localhost"

_pool = None
_pool_lock = threading.Lock()

def _get_pool():
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                import psycopg2
                from psycopg2 import pool
                _pool = pool.ThreadedConnectionPool(DB_POOL_MIN, DB_POOL_MAX, DATABASE_URL)
    return _pool

def _get_conn(connection_string: str = None):
    cs = connection_string or DATABASE_URL
    if not cs:
        raise ValueError("DATABASE_URL not configured. Set environment variable or pass connection_string.")
    if connection_string:
        import psycopg2
        return psycopg2.connect(cs)
    pool = _get_pool()
    conn = pool.getconn()
    try:
        # Validate the connection is alive
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        return conn
    except Exception:
        pool.putconn(conn, close=True)
        raise

def _put_conn(conn, connection_string: str = None):
    if connection_string:
        conn.close()
        return
    pool = _get_pool()
    pool.putconn(conn)

def _dict_cursor(conn):
    import psycopg2.extras
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

mcp = FastMCP("postgres", instructions="""
PostgreSQL database query tools.
Provides read-only SQL queries, table listing, schema inspection, and table schema resources.
Set DATABASE_URL environment variable or pass connection_string parameter.
Environment variables: DB_POOL_MIN (default 2), DB_POOL_MAX (default 10) control connection pool size.
""")

@mcp.tool(
    name="list_tables",
    description="List all tables in the database grouped by schema."
)
async def list_tables(connection_string: str = "") -> str:
    try:
        cache_key = f"mcp:pg:tables:{connection_string}"
        cached = cache_get(cache_key)
        if cached is not None:
            return cached
        conn = _get_conn(connection_string)
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                ORDER BY table_schema, table_name
            """)
            rows = cur.fetchall()
            cur.close()
            if not rows:
                return "(no tables found)"
            schemas = {}
            for schema, name in rows:
                schemas.setdefault(schema, []).append(name)
            parts = [f"{s}: {', '.join(tables)}" for s, tables in schemas.items()]
            cache_set(cache_key, "Tables:\n" + "\n".join(parts), ttl=3600)
            return "Tables:\n" + "\n".join(parts)
        finally:
            _put_conn(conn, connection_string)
    except ImportError:
        return "(psycopg2 not installed. Run: pip install psycopg2-binary)"
    except Exception as e:
        return f"(database error: {e})"

@mcp.tool(
    name="query",
    description="Execute a read-only SQL query and return results as JSON."
)
async def query(sql: str, connection_string: str = "", max_rows: int = 100) -> str:
    sql_upper = sql.strip().upper()
    if not sql_upper.startswith("SELECT") and not sql_upper.startswith("WITH") and not sql_upper.startswith("EXPLAIN"):
        return "(only SELECT/WITH/EXPLAIN queries are allowed for safety)"
    cache_key = f"mcp:pg:query:{connection_string}:{sql}:{max_rows}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached
    try:
        conn = _get_conn(connection_string)
        try:
            cur = _dict_cursor(conn)
            cur.execute("BEGIN TRANSACTION READ ONLY")
            cur.execute(sql)
            colnames = [desc[0] for desc in cur.description] if cur.description else []
            rows = cur.fetchmany(max_rows)
            cur.execute("ROLLBACK")
            cur.close()
            if not rows:
                return "(query returned no rows)"
            result = []
            for row in rows:
                cleaned = {}
                for k, v in row.items():
                    if isinstance(v, (bytes, bytearray)):
                        cleaned[k] = repr(v)[:200]
                    elif isinstance(v, str):
                        cleaned[k] = v[:1000]
                    elif v is None:
                        cleaned[k] = None
                    else:
                        cleaned[k] = v
                result.append(cleaned)
            output = json.dumps(result, indent=2, default=str, ensure_ascii=False)
            if len(rows) >= max_rows:
                output += f"\n\n(limited to {max_rows} rows)"
            cache_set(cache_key, output, ttl=300)
            return output
        finally:
            _put_conn(conn, connection_string)
    except ImportError:
        return "(psycopg2 not installed. Run: pip install psycopg2-binary)"
    except Exception as e:
        return f"(query error: {e})"

_re_query = query

@mcp.tool(
    name="run_query",
    description="Alias for query -- execute a read-only SQL query and return formatted text results."
)
async def run_query(sql: str, connection_string: str = "", max_rows: int = 50) -> str:
    return await _re_query(sql, connection_string, max_rows)

@mcp.tool(
    name="describe_table",
    description="Show detailed column information for a table (name, type, nullable, default)."
)
async def describe_table(table_name: str, connection_string: str = "") -> str:
    schema, tbl = ("public", table_name) if "." not in table_name else table_name.split(".", 1)
    try:
        cache_key = f"mcp:pg:describe:{connection_string}:{table_name}"
        cached = cache_get(cache_key)
        if cached is not None:
            return cached
        conn = _get_conn(connection_string)
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT column_name, data_type, is_nullable, column_default, character_maximum_length
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
            """, (schema, tbl))
            rows = cur.fetchall()
            cur.close()
            if not rows:
                return f"(table {schema}.{tbl} not found)"
            lines = [
                f"{'Column':25} {'Type':25} {'Nullable':10} {'Default':25} {'Len':10}",
                "-" * 95
            ]
            for col, typ, nullable, default, charlen in rows:
                maxlen = str(charlen) if charlen else ""
                lines.append(f"{col:25} {typ:25} {nullable:10} {str(default or ''):25} {maxlen:10}")
            cache_set(cache_key, "\n".join(lines), ttl=3600)
            return "\n".join(lines)
        finally:
            _put_conn(conn, connection_string)
    except ImportError:
        return "(psycopg2 not installed. Run: pip install psycopg2-binary)"
    except Exception as e:
        return f"(error: {e})"

@mcp.resource(
    uri="postgres://{table_name}/schema",
    name="Table Schema",
    description="JSON schema information for a database table",
    mime_type="application/json"
)
async def get_table_schema(table_name: str) -> str:
    schema, tbl = ("public", table_name) if "." not in table_name else table_name.split(".", 1)
    try:
        conn = _get_conn()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
            """, (schema, tbl))
            rows = cur.fetchall()
            cur.close()
            if not rows:
                return json.dumps({"error": f"table {schema}.{tbl} not found"})
            columns = [{
                "name": r[0],
                "type": r[1],
                "nullable": r[2] == "YES",
                "default": r[3]
            } for r in rows]
            return json.dumps({"table": f"{schema}.{tbl}", "columns": columns}, indent=2, ensure_ascii=False)
        finally:
            _put_conn(conn)
    except ImportError:
        return json.dumps({"error": "psycopg2 not installed"})
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.resource(
    uri="postgres://tables",
    name="All Tables",
    description="List of all tables in the database",
    mime_type="application/json"
)
async def get_all_tables() -> str:
    try:
        conn = _get_conn()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                ORDER BY table_schema, table_name
            """)
            rows = cur.fetchall()
            cur.close()
            tables = [f"{s}.{t}" if s != "public" else t for s, t in rows]
            return json.dumps({"tables": tables}, indent=2, ensure_ascii=False)
        finally:
            _put_conn(conn)
    except ImportError:
        return json.dumps({"error": "psycopg2 not installed"})
    except Exception as e:
        return json.dumps({"error": str(e)})

if __name__ == "__main__":
    if not DATABASE_URL:
        print("WARNING: DATABASE_URL is not set. Tools will fail until a connection_string is provided.")
    mcp.run(transport="stdio")
