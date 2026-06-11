import os
import subprocess
import json
from pathlib import Path
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("refactor", instructions="""
Smart Refactorer Server: Clean, format, and optimize code architecture.
Supports automated linting, unused import removal, and code style enforcement.
""")

@mcp.tool(name="clean_python_code", description="Automatically remove unused imports and format Python code using autoflake and black.")
async def clean_python_code(file_path: str) -> str:
    \"\"\"Runs autoflake and black on a file to clean it up.\"\"\"
    path = Path(file_path).expanduser()
    if not path.exists():
        return f"Error: File {file_path} not found."

    results = []
    # 1. Remove unused imports/variables
    try:
        subprocess.run([
            "autoflake", "--in-place", "--remove-all-unused-imports", 
            "--remove-unused-variables", str(path)
        ], check=True)
        results.append("✅ Unused imports/variables removed.")
    except Exception as e:
        results.append(f"⚠️ Autoflake failed: {e} (Make sure 'pip install autoflake' is done)")

    # 2. Format with Black
    try:
        subprocess.run(["black", str(path)], check=True)
        results.append("✅ Code formatted with Black.")
    except Exception as e:
        results.append(f"⚠️ Black failed: {e}")

    return "\n".join(results)

@mcp.tool(name="rename_symbol_project", description="Rename a variable or function across the entire project (simple regex-based).")
async def rename_symbol_project(old_name: str, new_name: str, directory: str = ".") -> str:
    \"\"\"Renames symbols in multiple files. Use with caution.\"\"\"
    count = 0
    dir_path = Path(directory).expanduser()
    
    # Simple recursive replacement in .py and .js files
    for ext in ['*.py', '*.js', '*.ts']:
        for path in dir_path.rglob(ext):
            if 'node_modules' in str(path) or '.git' in str(path):
                continue
            
            content = path.read_text(encoding='utf-8', errors='ignore')
            # Use regex to match whole words only
            new_content, n = re.subn(rf'\b{old_name}\b', new_name, content)
            if n > 0:
                path.write_text(new_content, encoding='utf-8')
                count += n
                
    return f"✅ Renamed '{old_name}' to '{new_name}' in {count} locations across the project."

@mcp.tool(name="check_code_smells", description="Scan for long functions or deep nesting (simple analysis).")
async def check_code_smells(file_path: str) -> str:
    \"\"\"Basic complexity check.\"\"\"
    path = Path(file_path).expanduser()
    content = path.read_text(encoding='utf-8').splitlines()
    
    issues = []
    for i, line in enumerate(content, 1):
        if len(line) > 100:
            issues.append(f"Line {i}: Very long line ({len(line)} chars).")
        if line.count('    ') > 4 or line.count('\t') > 4:
            issues.append(f"Line {i}: Deep nesting detected.")
            
    return "\n".join(issues) if issues else "✅ No obvious code smells detected."

import re # Needed for rename_symbol_project
if __name__ == "__main__":
    mcp.run(transport="stdio")
