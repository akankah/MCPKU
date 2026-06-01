import os, glob, json, base64, difflib, stat, mimetypes, time, fnmatch
from datetime import datetime
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("filesystem", instructions="""
File system operations: read, write, edit, list, search, grep, move, copy, delete, tree, metadata.
Access is restricted to allowed directories only.
""")

# Normalize allowed dirs with trailing separator to prevent prefix collisions
def _norm_allowed(d):
    rp = os.path.realpath(d)
    return rp if rp.endswith(os.sep) else rp + os.sep

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_extra = os.environ.get("MCP_EXTRA_ALLOWED_DIR", "").strip()

ALLOWED_PREFIXES = tuple(_norm_allowed(p) for p in [
    "C:\\",
    BASE_DIR,
    os.path.join(BASE_DIR, "..", ".kilo"),
] + ([_extra] if _extra else []))

def _allowed(path: str) -> bool:
    if not os.path.exists(path):
        rp = os.path.realpath(os.path.dirname(path))
        if not rp.endswith(os.sep): rp += os.sep
        return any(rp.startswith(ap) for ap in ALLOWED_PREFIXES)
    rp = os.path.realpath(path)
    if not rp.endswith(os.sep): rp += os.sep
    return any(rp.startswith(ap) for ap in ALLOWED_PREFIXES)

def _ensure_dir(path: str):
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

def _read_file_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def _format_timestamp(ts: float) -> str:
    return datetime.fromtimestamp(ts).isoformat()

# ── Read ────────────────────────────────────────────────────────────────

@mcp.tool(
    name="read_file",
    description="Read file contents. Use offset/limit for line-range reading of large files."
)
async def read_file(path: str, offset: int = None, limit: int = None) -> str:
    if not os.path.exists(path):
        return f"(not found: {path})"
    if not _allowed(path):
        return "(access denied: path not allowed)"
    try:
        with open(path, "r", encoding="utf-8") as f:
            if offset is not None:
                for _ in range(offset):
                    f.readline()
            if limit is not None:
                return "".join(f.readline() for _ in range(limit))
            return f.read()
    except UnicodeDecodeError:
        return "(binary file - use read_media_file for binary data)"
    except Exception as e:
        return f"(error reading {path}: {e})"

@mcp.tool(
    name="read_media_file",
    description="Read an image or audio file and return as base64 data with MIME type."
)
async def read_media_file(path: str) -> str:
    if not os.path.exists(path):
        return f"(not found: {path})"
    if not _allowed(path):
        return "(access denied: path not allowed)"
    try:
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
        return f"data:{mime};base64,{data}"
    except Exception as e:
        return f"(error reading media {path}: {e})"

@mcp.tool(
    name="read_multiple_files",
    description="Read multiple files simultaneously. Failed reads won't stop the entire operation."
)
async def read_multiple_files(paths: list) -> str:
    results = []
    for p in paths:
        if not os.path.exists(p):
            results.append(f"--- {p} ---\n(not found)")
        elif not _allowed(p):
            results.append(f"--- {p} ---\n(access denied)")
        else:
            try:
                content = _read_file_text(p)
                results.append(f"--- {p} ---\n{content}")
            except UnicodeDecodeError:
                results.append(f"--- {p} ---\n(binary file)")
            except Exception as e:
                results.append(f"--- {p} ---\n(error: {e})")
    return "\n\n".join(results)

# ── Write & Edit ────────────────────────────────────────────────────────

@mcp.tool(
    name="write_file",
    description="Create new file or overwrite existing (use with caution)."
)
async def write_file(path: str, content: str) -> str:
    if not _allowed(path):
        return "(access denied: path not allowed)"
    try:
        _ensure_dir(path)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"(written: {path})"
    except Exception as e:
        return f"(error writing {path}: {e})"

@mcp.tool(
    name="append_file",
    description="Append content to end of an existing file."
)
async def append_file(path: str, content: str) -> str:
    if not os.path.exists(path):
        return f"(not found: {path})"
    if not _allowed(path):
        return "(access denied: path not allowed)"
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(content)
        return f"(appended: {path})"
    except Exception as e:
        return f"(error appending to {path}: {e})"

@mcp.tool(
    name="edit_file",
    description="Make selective edits using pattern matching. Supports dry-run to preview changes."
)
async def edit_file(path: str, edits: list, dry_run: bool = False) -> str:
    if not os.path.exists(path):
        return f"(not found: {path})"
    if not _allowed(path):
        return "(access denied: path not allowed)"
    try:
        original = _read_file_text(path)
        result = original

        for edit in edits:
            old = edit.get("oldText", "")
            new = edit.get("newText", "")
            count = result.count(old)
            if count == 0:
                return f"(error: pattern not found in {path}: {repr(old[:50])})"
            result = result.replace(old, new, 1)

        if dry_run:
            diff = "\n".join(difflib.unified_diff(
                original.splitlines(), result.splitlines(),
                fromfile=f"a/{path}", tofile=f"b/{path}", lineterm=""
            ))
            return f"[DRY RUN] Changes for {path}:\n{diff}" if diff else f"[DRY RUN] No changes for {path}"

        with open(path, "w", encoding="utf-8") as f:
            f.write(result)
        diff = "\n".join(difflib.unified_diff(
            original.splitlines(), result.splitlines(),
            fromfile=f"a/{path}", tofile=f"b/{path}", lineterm=""
        ))
        return diff if diff else "(no changes made)"

    except Exception as e:
        return f"(error editing {path}: {e})"

# ── Directory ops ───────────────────────────────────────────────────────

@mcp.tool(
    name="create_directory",
    description="Create new directory or ensure it exists. Creates parent directories if needed."
)
async def create_directory(path: str) -> str:
    if not _allowed(path):
        return "(access denied: path not allowed)"
    try:
        os.makedirs(path, exist_ok=True)
        return f"(directory ready: {path})"
    except Exception as e:
        return f"(error creating directory {path}: {e})"

@mcp.tool(
    name="list_directory",
    description="List directory contents with [FILE] or [DIR] prefixes."
)
async def list_directory(path: str) -> str:
    if not os.path.isdir(path):
        return f"(not a directory: {path})"
    if not _allowed(path):
        return "(access denied: path not allowed)"
    try:
        entries = os.listdir(path)
        lines = []
        for e in sorted(entries):
            fp = os.path.join(path, e)
            if os.path.isdir(fp):
                lines.append(f"[DIR]  {e}")
            else:
                lines.append(f"[FILE] {e}")
        return "\n".join(lines) if lines else "(empty directory)"
    except Exception as ex:
        return f"(error listing {path}: {ex})"

@mcp.tool(
    name="list_directory_detailed",
    description="List directory with file sizes, modified time, and sort options."
)
async def list_directory_detailed(path: str, sort_by: str = "name") -> str:
    if not os.path.isdir(path):
        return f"(not a directory: {path})"
    if not _allowed(path):
        return "(access denied: path not allowed)"
    try:
        entries = []
        total_files = 0
        total_dirs = 0
        total_size = 0
        for e in os.listdir(path):
            fp = os.path.join(path, e)
            if os.path.isdir(fp):
                total_dirs += 1
                entries.append(("dir", e, None, None))
            else:
                sz = os.path.getsize(fp)
                mt = os.path.getmtime(fp)
                total_files += 1
                total_size += sz
                entries.append(("file", e, sz, mt))

        if sort_by == "size":
            entries.sort(key=lambda x: (x[0], x[2] if x[2] is not None else 0))
        elif sort_by == "date":
            entries.sort(key=lambda x: (x[0], x[3] if x[3] is not None else 0), reverse=True)
        else:
            entries.sort(key=lambda x: x[1].lower())

        lines = []
        for etype, name, sz, mt in entries:
            if etype == "dir":
                lines.append(f"[DIR]  {name}")
            elif sz is not None:
                size_str = f"{sz/1048576:.1f} MB" if sz >= 1048576 else f"{sz/1024:.1f} KB" if sz >= 1024 else f"{sz} B"
                date_str = _format_timestamp(mt) if mt else ""
                lines.append(f"[FILE] {name:<40} {size_str:>10}  {date_str}")

        summary = f"\n---\nFiles: {total_files}, Dirs: {total_dirs}, Total size: {total_size/1024:.1f} KB"
        return "\n".join(lines) + summary if lines else "(empty directory)"
    except Exception as ex:
        return f"(error listing {path}: {ex})"

@mcp.tool(
    name="directory_tree",
    description="Get recursive JSON tree structure of directory contents."
)
async def directory_tree(path: str, exclude_patterns: list = None, depth: int = None) -> str:
    if not os.path.isdir(path):
        return f"(not a directory: {path})"
    if not _allowed(path):
        return "(access denied: path not allowed)"
    try:
        exclude_set = set()
        if exclude_patterns:
            for ep in exclude_patterns:
                exclude_set.update(glob.glob(os.path.join(path, ep), recursive=True))
        result = _build_tree(path, path, exclude_set, depth)
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as ex:
        return f"(error building tree for {path}: {ex})"

def _build_tree(root: str, current: str, exclude: set, max_depth: int = None, _depth: int = 0) -> list:
    if max_depth is not None and _depth >= max_depth:
        return [{"name": "...", "type": "truncated"}]
    entries = []
    try:
        for e in sorted(os.listdir(current)):
            fp = os.path.join(current, e)
            if fp in exclude:
                continue
            entry = {"name": e}
            if os.path.isdir(fp):
                entry["type"] = "directory"
                children = _build_tree(root, fp, exclude, max_depth, _depth + 1)
                entry["children"] = children
            else:
                entry["type"] = "file"
                try:
                    entry["size"] = os.path.getsize(fp)
                except OSError:
                    pass
            entries.append(entry)
    except PermissionError:
        pass
    return entries

# ── File ops ────────────────────────────────────────────────────────────

@mcp.tool(
    name="copy_file",
    description="Copy file or directory. Fails if destination exists unless overwrite=True."
)
async def copy_file(source: str, destination: str, overwrite: bool = False) -> str:
    if not os.path.exists(source):
        return f"(not found: {source})"
    if not _allowed(source) or not _allowed(destination):
        return "(access denied: path not allowed)"
    if os.path.exists(destination) and not overwrite:
        return f"(error: destination exists: {destination})"
    try:
        _ensure_dir(destination)
        if os.path.isdir(source):
            import shutil
            shutil.copytree(source, destination, dirs_exist_ok=overwrite)
            return f"(copied directory: {source} -> {destination})"
        else:
            import shutil
            shutil.copy2(source, destination)
            return f"(copied: {source} -> {destination})"
    except Exception as e:
        return f"(error copying {source} -> {destination}: {e})"

@mcp.tool(
    name="move_file",
    description="Move or rename files and directories. Fails if destination exists unless overwrite=True."
)
async def move_file(source: str, destination: str, overwrite: bool = False) -> str:
    if not os.path.exists(source):
        return f"(not found: {source})"
    if not _allowed(source) or not _allowed(destination):
        return "(access denied: path not allowed)"
    if os.path.exists(destination) and not overwrite:
        return f"(error: destination exists: {destination})"
    try:
        _ensure_dir(destination)
        if os.path.exists(destination) and overwrite:
            if os.path.isdir(destination):
                import shutil
                shutil.rmtree(destination)
            else:
                os.remove(destination)
        os.rename(source, destination)
        return f"(moved: {source} -> {destination})"
    except Exception as e:
        return f"(error moving {source} -> {destination}: {e})"

@mcp.tool(
    name="delete_file",
    description="Delete file or empty directory. Use recursive=True for non-empty directories."
)
async def delete_file(path: str, recursive: bool = False) -> str:
    if not os.path.exists(path):
        return f"(not found: {path})"
    if not _allowed(path):
        return "(access denied: path not allowed)"
    if path.strip("\\ ").lower() in [ap.lower() for ap in ALLOWED_PREFIXES]:
        return "(error: cannot delete an allowed root directory)"
    try:
        if os.path.isdir(path):
            if recursive:
                import shutil
                shutil.rmtree(path)
                return f"(deleted directory: {path})"
            else:
                os.rmdir(path)
                return f"(deleted empty directory: {path})"
        else:
            os.remove(path)
            return f"(deleted: {path})"
    except OSError as e:
        return f"(error: {e})"
    except Exception as e:
        return f"(error deleting {path}: {e})"

# ── Search ──────────────────────────────────────────────────────────────

@mcp.tool(
    name="search_files",
    description="Recursively search for files/directories using glob pattern matching."
)
async def search_files(path: str, pattern: str, exclude_patterns: list = None) -> str:
    if not os.path.isdir(path):
        return f"(not a directory: {path})"
    if not _allowed(path):
        return "(access denied: path not allowed)"
    try:
        matches = sorted(glob.glob(os.path.join(path, pattern), recursive=True))[:200]
        if exclude_patterns:
            excluded = set()
            for ep in exclude_patterns:
                excluded.update(glob.glob(os.path.join(path, ep), recursive=True))
            matches = [m for m in matches if m not in excluded]
        if not matches:
            return "(no matches)"
        return "\n".join(matches)
    except Exception as ex:
        return f"(error searching: {ex})"

@mcp.tool(
    name="grep_files",
    description="Search file contents recursively with regex pattern. Returns file:line matches."
)
async def grep_files(path: str, pattern: str, include: str = None, exclude: str = None, max_results: int = 50, context_lines: int = 0) -> str:
    if not os.path.isdir(path):
        return f"(not a directory: {path})"
    if not _allowed(path):
        return "(access denied: path not allowed)"
    import re
    try:
        re_pat = re.compile(pattern)
    except re.error as e:
        return f"(invalid regex: {e})"
    results = []
    try:
        for root, dirs, files in os.walk(path):
            if exclude and fnmatch.fnmatch(root, os.path.join(path, exclude)):
                dirs[:] = []
                continue
            for fname in sorted(files):
                if include and not fnmatch.fnmatch(fname, include):
                    continue
                if exclude and fnmatch.fnmatch(fname, exclude):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        for i, line in enumerate(f, 1):
                            if re_pat.search(line):
                                line_str = line.rstrip("\n\r")
                                if context_lines > 0:
                                    results.append(f"{fpath}:{i}:{line_str}")
                                else:
                                    results.append(f"{fpath}:{i}:{line_str[:200]}")
                                if len(results) >= max_results:
                                    return "Found {len(results)} matches:\n" + "\n".join(results) + "\n...(truncated at max_results)"
                except (UnicodeDecodeError, OSError):
                    pass
    except PermissionError:
        pass
    if not results:
        return "(no matches)"
    return f"Found {len(results)} matches:\n" + "\n".join(results)

@mcp.tool(
    name="glob_pattern",
    description="Match paths against a glob pattern and return matching paths."
)
async def glob_pattern(pattern: str, root: str = None) -> str:
    base = root or "."
    if not _allowed(base):
        return "(access denied: path not allowed)"
    try:
        matches = sorted(glob.glob(os.path.join(base, pattern), recursive=True))[:200]
        if not matches:
            return "(no matches)"
        return "\n".join(matches)
    except Exception as e:
        return f"(error: {e})"

# ── Metadata ────────────────────────────────────────────────────────────

@mcp.tool(
    name="get_file_info",
    description="Get detailed file/directory metadata: size, times, type, permissions."
)
async def get_file_info(path: str) -> str:
    if not os.path.exists(path):
        return f"(not found: {path})"
    if not _allowed(path):
        return "(access denied: path not allowed)"
    try:
        st = os.stat(path)
        ftype = "directory" if os.path.isdir(path) else "file"
        size = st.st_size
        perms = stat.filemode(st.st_mode)
        info = (
            f"Path: {os.path.realpath(path)}\n"
            f"Type: {ftype}\n"
            f"Size: {size:,} bytes"
        )
        if ftype == "file":
            if size >= 1048576:
                info += f" ({size/1048576:.1f} MB)"
            elif size >= 1024:
                info += f" ({size/1024:.1f} KB)"
        info += f"\n"
        info += f"Created:   {_format_timestamp(st.st_ctime)}\n"
        info += f"Modified:  {_format_timestamp(st.st_mtime)}\n"
        info += f"Accessed:  {_format_timestamp(st.st_atime)}\n"
        info += f"Permissions: {perms}"
        return info
    except Exception as e:
        return f"(error getting info for {path}: {e})"

@mcp.tool(
    name="path_exists",
    description="Check if a path exists and whether it is a file or directory."
)
async def path_exists(path: str) -> str:
    if not _allowed(path):
        return json.dumps({"exists": False, "reason": "access denied"})
    if not os.path.exists(path):
        return json.dumps({"exists": False, "path": path})
    return json.dumps({
        "exists": True,
        "path": os.path.realpath(path),
        "type": "directory" if os.path.isdir(path) else "file",
        "size": os.path.getsize(path) if os.path.isfile(path) else None
    })

@mcp.tool(
    name="list_allowed_directories",
    description="List all directories the server is allowed to access."
)
async def list_allowed_directories() -> str:
    lines = [f"  {d}" for d in ALLOWED_PREFIXES]
    return f"Allowed directories ({len(ALLOWED_PREFIXES)}):\n" + "\n".join(lines)

@mcp.tool(
    name="diff_files",
    description="Show unified diff between two files or between file and string content."
)
async def diff_files(path1: str, path2: str = None, content2: str = None) -> str:
    if not os.path.exists(path1):
        return f"(not found: {path1})"
    if not _allowed(path1):
        return "(access denied)"
    try:
        c1 = _read_file_text(path1)
        if path2:
            if not _allowed(path2):
                return "(access denied)"
            c2 = _read_file_text(path2)
        elif content2 is not None:
            c2 = content2
        else:
            return "(error: specify either path2 or content2)"
        diff = "\n".join(difflib.unified_diff(
            c1.splitlines(), c2.splitlines(),
            fromfile=path1, tofile=path2 or "(new)", lineterm=""
        ))
        return diff if diff else "(files are identical)"
    except Exception as e:
        return f"(error diffing: {e})"

if __name__ == "__main__":
    mcp.run(transport="stdio")
