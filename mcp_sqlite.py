import os, sys, json, sqlite3, asyncio, re
from pathlib import Path
from contextlib import closing
from functools import partial
from concurrent.futures import ThreadPoolExecutor
from mcp.server.fastmcp import FastMCP

if sys.platform == "win32" and os.environ.get("PYTHONIOENCODING") is None:
    try:
        sys.stdin.reconfigure(encoding="utf-8")
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

mcp = FastMCP("sqlite", instructions="""
SQLite database server: query, create tables, list schemas, analyze data,
and append business insights to a live memo resource (memo://insights).
""")

DB_PATH = os.environ.get("SQLITE_DB_PATH", "")
_insights: list[str] = []

# Executor khusus untuk blocking sqlite3 — tidak block event loop
_executor = None


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="sqlite")
    return _executor


def _validate_identifier(name: str) -> str:
    """Return safe quoted identifier, raise ValueError jika tidak valid."""
    # Hanya izinkan nama tabel/kolom yang valid (alphanumeric + underscore)
    if not re.match(r'^[A-Za-z_][A-Za-z0-9_ ]*$', name):
        raise ValueError(f"Invalid identifier: {name!r}")
    # Quote dengan double-quote (SQL standard)
    return f'"{name}"'


class SqliteDB:
    def __init__(self, db_path: str):
        self.db_path = str(Path(db_path).expanduser())
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def _execute_sync(self, query: str, params: tuple = ()) -> list:
        """Synchronous execute — dijalankan di thread pool, bukan di event loop."""
        with closing(sqlite3.connect(self.db_path, timeout=10)) as conn:
            conn.row_factory = sqlite3.Row
            # WAL mode: concurrent reads lebih baik
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            with closing(conn.cursor()) as cur:
                cur.execute(query, params)
                keyword = query.strip().upper().split()[0]
                if keyword in ("INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER"):
                    conn.commit()
                    return [{"affected_rows": cur.rowcount}]
                return [dict(row) for row in cur.fetchall()]

    async def execute(self, query: str, params: tuple = ()) -> list:
        """Async wrapper — jalankan _execute_sync di thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _get_executor(),
            partial(self._execute_sync, query, params)
        )


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
        results = await db.execute(query)
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
        results = await db.execute(query)
        return json.dumps(results, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"(error: {e})"


@mcp.tool(name="create_table", description="Create a new table in the SQLite database.")
async def create_table(query: str, db_path: str = "") -> str:
    if not query.strip().upper().startswith("CREATE TABLE"):
        return "(only CREATE TABLE statements allowed)"
    try:
        db = _get_db(db_path)
        await db.execute(query)
        return "Table created successfully"
    except Exception as e:
        return f"(error: {e})"


@mcp.tool(name="list_tables", description="List all tables in the SQLite database.")
async def list_tables(db_path: str = "") -> str:
    try:
        db = _get_db(db_path)
        results = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        if not results:
            return "(no tables)"
        names = [r["name"] for r in results]
        return "Tables:\n" + "\n".join(f"  - {n}" for n in names)
    except Exception as e:
        return f"(error: {e})"


@mcp.tool(name="describe_table", description="Get schema info for a specific table via PRAGMA.")
async def describe_table(table_name: str, db_path: str = "") -> str:
    try:
        safe_name = _validate_identifier(table_name)
    except ValueError as e:
        return f"(error: {e})"
    try:
        db = _get_db(db_path)
        # Gunakan identifier yang sudah di-quote, bukan f-string langsung
        results = await db.execute(f"PRAGMA table_info({safe_name})")
        if not results:
            return f"(table not found: {table_name})"
        lines = [
            f"{'CID':4} {'Name':20} {'Type':15} {'Nullable':8} {'Default':15} {'PK':3}",
            "-" * 65
        ]
        for r in results:
            lines.append(
                f"{r['cid']:4} {r['name']:20} {r['type']:15} "
                f"{'YES' if r['notnull']==0 else 'NO':8} "
                f"{str(r['dflt_value'] or ''):15} {r['pk']:3}"
            )
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
