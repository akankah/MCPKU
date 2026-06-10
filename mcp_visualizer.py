import os
import sys
import json
import sqlite3
import asyncio
from pathlib import Path
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("visualizer", instructions="""
Database Visualizer Server: Generate Mermaid ERD diagrams from database schemas.
Works with SQLite and (soon) PostgreSQL.
""")

def _get_mermaid_for_sqlite(db_path: str) -> str:
    \"\"\"Reads SQLite schema and generates Mermaid ERD string.\"\"\"
    if not os.path.exists(db_path):
        return f"Error: Database file not found at {db_path}"
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [row['name'] for row in cursor.fetchall()]
    
    mermaid = "erDiagram\n"
    
    for table in tables:
        mermaid += f"    {table} {{\n"
        # Get columns
        cursor.execute(f"PRAGMA table_info(\"{table}\")")
        columns = cursor.fetchall()
        for col in columns:
            pk = "PK" if col['pk'] else ""
            mermaid += f"        {col['type']} {col['name']} {pk}\n"
        mermaid += "    }\n"
        
        # Get foreign keys for relations
        cursor.execute(f"PRAGMA foreign_key_list(\"{table}\")")
        fks = cursor.fetchall()
        for fk in fks:
            # Format: table1 ||--o{ table2 : "relation"
            mermaid += f"    {table} }}o--|| {fk['table']} : \"{fk['from']}\"\n"
            
    conn.close()
    return mermaid

@mcp.tool(name="visualize_sqlite", description="Generate a Mermaid ERD diagram for a SQLite database.")
async def visualize_sqlite(db_path: str) -> str:
    \"\"\"Generates a Mermaid diagram from a SQLite database.\"\"\"
    try:
        mermaid_code = _get_mermaid_for_sqlite(db_path)
        
        # Save to a temporary markdown file for preview
        output_dir = Path("E:/MCPKU/output/diagrams")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        file_name = f"erd_{Path(db_path).stem}.md"
        output_path = output_dir / file_name
        
        with open(output_path, "w") as f:
            f.write(f"# ER Diagram for {Path(db_path).name}\\n\\n```mermaid\\n{mermaid_code}\\n```")
            
        return f"Mermaid ERD generated successfully!\\n\\nOutput file: {output_path}\\n\\nCode:\\n{mermaid_code}"
    except Exception as e:
        return f"Error generating visualization: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
