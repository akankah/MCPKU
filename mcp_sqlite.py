import os, sys, json, sqlite3
from pathlib import Path
from contextlib import closing
from mcp.server.fastmcp import FastMCP

if sys.platform == "win32" and os.environ.get('PYTHONIOENCODING') is None:
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

mcp = FastMCP("sqlite", instructions="""
SQLite database server: query, create tables, list schemas, analyze data,
and append business insights to a live memo resource (memo://insights).
""")

DB_PATH = os.environ.get("SQLITE_DB_PATH", "")
_insights: list[str] = []

class SqliteDB:
    def __init__(self, db_path: str):
        self.db_path = str(Path(db_path).expanduser())
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def execute(self, query: str) -> list:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            with closing(conn.cursor()) as cur:
                cur.execute(query)
                if query.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER')):
                    conn.commit()
                    return [{"affected_rows": cur.rowcount}]
                return [dict(row) for row in cur.fetchall()]

def _get_db(db_path: str = "") -> SqliteDB:
    path = db_path or DB_PATH
    if not path:
        raise ValueError("SQLITE_DB_PATH not configured. Set env or pass db_path.")
    return SqliteDB(path)

def _synthesize_memo() -> str:
    if not _insights:
        return "No business insights have been discovered yet."
    lines = "\n".join(f"- {insight}" for insight in _insights)
    memo = "Business Intelligence Memo\n\nKey Insights Discovered:\n\n" + lines
    if len(_insights) > 1:
        memo += f"\n\nSummary:\nAnalysis has revealed {len(_insights)} key business insights."
    return memo

@mcp.tool(name="read_query", description="Execute a SELECT query on the SQLite database.")
async def read_query(query: str, db_path: str = "") -> str:
    if not query.strip().upper().startswith("SELECT"):
        return "(only SELECT queries are allowed for read_query)"
    try:
        db = _get_db(db_path)
        results = db.execute(query)
        return json.dumps(results, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"(error: {e})"

@mcp.tool(name="write_query", description="Execute INSERT, UPDATE, or DELETE query on SQLite.")
async def write_query(query: str, db_path: str = "") -> str:
    q = query.strip().upper()
    if q.startswith("SELECT"):
        return "(SELECT not allowed for write_query)"
    if not q.startswith(("INSERT", "UPDATE", "DELETE")):
        return "(only INSERT/UPDATE/DELETE allowed)"
    try:
        db = _get_db(db_path)
        results = db.execute(query)
        return json.dumps(results, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"(error: {e})"

@mcp.tool(name="create_table", description="Create a new table in the SQLite database.")
async def create_table(query: str, db_path: str = "") -> str:
    if not query.strip().upper().startswith("CREATE TABLE"):
        return "(only CREATE TABLE statements allowed)"
    try:
        db = _get_db(db_path)
        db.execute(query)
        return "Table created successfully"
    except Exception as e:
        return f"(error: {e})"

@mcp.tool(name="list_tables", description="List all tables in the SQLite database.")
async def list_tables(db_path: str = "") -> str:
    try:
        db = _get_db(db_path)
        results = db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        if not results:
            return "(no tables)"
        names = [r["name"] for r in results]
        return "Tables:\n" + "\n".join(f"  - {n}" for n in names)
    except Exception as e:
        return f"(error: {e})"

@mcp.tool(name="describe_table", description="Get schema info for a specific table via PRAGMA.")
async def describe_table(table_name: str, db_path: str = "") -> str:
    try:
        db = _get_db(db_path)
        results = db.execute(f"PRAGMA table_info({json.dumps(table_name)})")
        if not results:
            return f"(table not found: {table_name})"
        lines = [f"{'CID':4} {'Name':20} {'Type':15} {'Nullable':8} {'Default':15} {'PK':3}", "-"*65]
        for r in results:
            lines.append(f"{r['cid']:4} {r['name']:20} {r['type']:15} {'YES' if r['notnull']==0 else 'NO':8} {str(r['dflt_value'] or ''):15} {r['pk']:3}")
        return "\n".join(lines)
    except Exception as e:
        return f"(error: {e})"

@mcp.tool(name="append_insight", description="Add a business insight to the memo resource.")
async def append_insight(insight: str) -> str:
    _insights.append(insight)
    return "Insight added to memo"

@mcp.resource(
    uri="memo://insights",
    name="Business Insights Memo",
    description="A living document of discovered business insights",
    mime_type="text/plain"
)
async def insights_memo() -> str:
    return _synthesize_memo()

if __name__ == "__main__":
    if not DB_PATH:
        print("WARNING: SQLITE_DB_PATH is not set. Pass db_path to tools.", file=sys.stderr)
    mcp.run(transport="stdio")
