"""
mcp_diagnostics.py — MCPKU Error Diagnostics Server
=====================================================
MCP server untuk membaca, parse, dan klasifikasi error secara otomatis.
Terintegrasi dengan opencode sebagai MCP tool.

Tools yang disediakan:
  - parse_traceback        : Parse Python/Node.js/Rust traceback dari string
  - read_log_tail          : Baca N baris terakhir dari file log + parse error
  - watch_stderr           : Jalankan command, tangkap stderr, parse hasilnya
  - classify_error         : Klasifikasi tipe error dari pesan error apapun
  - scan_project_errors    : Scan seluruh file .log/.err dalam folder
  - explain_error          : Beri konteks + saran fix berdasarkan error type
  - get_error_history      : Lihat riwayat error yang sudah dibaca di session ini

Cara daftarkan di opencode.jsonc:
  "diagnostics": {
    "type": "local",
    "command": ["python", "E:/MCPKU/mcp_diagnostics.py"],
    "enabled": true
  }

Requirements: hanya stdlib Python 3.10+, tidak ada dependensi tambahan.
"""

import asyncio
import os
import re
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Optional
from mcp.server.fastmcp import FastMCP

# ── Path allowlist (sama dengan mcp_filesystem) ─────────────────────────────
_FS_ALLOW_ALL = os.environ.get("MCP_FS_ALLOW_ALL", "0") == "1"
_extra = os.environ.get("MCP_EXTRA_ALLOWED_DIR", "").strip()
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if os.name == "nt":
    _DEFAULT_PATHS = ["C:\\", "D:\\", "E:\\"]
else:
    _DEFAULT_PATHS = ["/home", "/tmp", "/workspace"]
_ALLOWED_PREFIXES = tuple(
    os.path.normpath(p) + os.sep
    for p in (_DEFAULT_PATHS + [_BASE_DIR] + ([_extra] if _extra else []))
)

def _is_path_allowed(path: str) -> bool:
    if _FS_ALLOW_ALL:
        return True
    resolved = os.path.normpath(os.path.abspath(path))
    return any(resolved.startswith(ap) for ap in _ALLOWED_PREFIXES)

mcp = FastMCP(
    "diagnostics",
    instructions=(
        "Error diagnostics server. You MUST automatically call parse_traceback "
        "or classify_error whenever you detect ANY error, exception, traceback, "
        "or crash in command output — do NOT wait for the user to ask. "
        "Also supports reading log files (read_log_tail), scanning entire log "
        "folders (scan_project_errors), running commands with stderr capture "
        "(watch_stderr), and providing fix explanations (explain_error). "
        "Track error history with get_error_history.\n\n"
        "AUTOFALLBACK RULE (mandatory):\n"
        "1. If classify_error returns an UNKNOWN / rare error type or version-specific "
        "message you cannot recognize from training data → you MUST call websearch "
        "('python <error_type> 2025 fix' or '<package> <error>') BEFORE suggesting a fix.\n"
        "2. If parse_traceback shows a library/module version mismatch (e.g. "
        "AttributeError on a method you remember differently) → call websearch FIRST.\n"
        "3. If explain_error cannot map the error to a known fix strategy → call websearch.\n"
        "Skip websearch ONLY for: standard well-known errors (ImportError, "
        "ModuleNotFoundError, FileNotFoundError, IndentationError, SyntaxError) "
        "where the fix is unambiguous and library-version-independent."
    ),
)

# ── Session error history ────────────────────────────────────────────────────
_error_history: list[dict] = []

_STATELESS = os.environ.get("AUTOFIX_STATELESS", "0") == "1"

def _record(error_type: str, message: str, source: str = "") -> None:
    if _STATELESS:
        return
    _error_history.append({
        "timestamp": datetime.now().isoformat(),
        "type": error_type,
        "message": message[:300],
        "source": source,
    })
    # Keep last 100 entries only
    if len(_error_history) > 100:
        _error_history.pop(0)


# ── Error type definitions ───────────────────────────────────────────────────
ERROR_PATTERNS = {
    # Python
    "Python.SyntaxError":      r"\bSyntaxError\b",
    "Python.IndentationError": r"\bIndentationError\b",
    "Python.NameError":        r"\bNameError\b",
    "Python.TypeError":        r"\bTypeError\b",
    "Python.AttributeError":   r"\bAttributeError\b",
    "Python.ImportError":      r"\b(ImportError|ModuleNotFoundError)\b",
    "Python.FileNotFound":     r"\bFileNotFoundError\b",
    "Python.KeyError":         r"\bKeyError\b",
    "Python.IndexError":       r"\bIndexError\b",
    "Python.ValueError":       r"\bValueError\b",
    "Python.RuntimeError":     r"\bRuntimeError\b",
    "Python.RecursionError":   r"\bRecursionError\b",
    "Python.MemoryError":      r"\bMemoryError\b",
    "Python.PermissionError":  r"\bPermissionError\b",
    "Python.TimeoutError":     r"\bTimeoutError\b",
    "Python.AssertionError":   r"\bAssertionError\b",
    "Python.ZeroDivision":     r"\bZeroDivisionError\b",
    "Python.StopIteration":    r"\bStopIteration\b",
    "Python.OSError":          r"\bOSError\b",
    # Node.js / JavaScript
    "JS.TypeError":            r"\bTypeError(?:\s*:|\s+(?:Cannot|is not|must))",
    "JS.ReferenceError":       r"\bReferenceError\b",
    "JS.SyntaxError":          r"\bSyntaxError(?:\s*:)",
    "JS.RangeError":           r"\bRangeError\b",
    "JS.URIError":             r"\bURIError\b",
    "JS.ModuleNotFound":       r"Cannot find module",
    "JS.UnhandledRejection":   r"UnhandledPromiseRejection",
    "JS.ENOENT":               r"ENOENT(?:: no such file)",
    "JS.EACCES":               r"EACCES(?:: permission denied)",
    "JS.EADDRINUSE":           r"EADDRINUSE",
    # Rust
    "Rust.Panic":              r"\bthread '.*' panicked(?: at '.*?')?(?: at \S+:\d+:\d+)?",
    "Rust.CompileError":       r"error\[E\d+\]",
    "Rust.BorrowError":        r"cannot borrow|borrow checker",
    # Go
    "Go.Panic":                r"goroutine \d+ \[",
    "Go.BuildError":           r"\.go:\d+:\d+:.*error:",
    # HTTP / API
    "HTTP.4xx":                r"\b4\d\d\b.*(?:error|not found|unauthorized|forbidden)",
    "HTTP.5xx":                r"\b5\d\d\b.*(?:error|internal server|bad gateway)",
    # Database
    "DB.ConnectionError":      r"(?:connection refused|could not connect|FATAL.*database)",
    "DB.Syntax":               r"(?:SQL syntax|near \".*\": syntax error)",
    "DB.UniqueViolation":      r"(?:unique constraint|duplicate key|UNIQUE.*failed)",
    "DB.ForeignKey":           r"foreign key constraint",
    # General
    "General.Timeout":         r"(?:timed? ?out|deadline exceeded|ETIMEDOUT)",
    "General.OOM":             r"(?:out of memory|OOM|killed.*memory)",
    "General.SegFault":        r"(?:segmentation fault|SIGSEGV|core dumped)",
    "General.Permission":      r"(?:permission denied|access denied|EPERM)",
    "General.NetworkError":    r"(?:connection reset|broken pipe|network unreachable|ECONNREFUSED)",
    # MCP (opencode) specific
    "MCP.Timeout":             r"Operation timed out after \d+ms",
    "MCP.RequestTimeout":      r"MCP error -32001: Request timed out",
    "MCP.SpawnFailed":         r"Unrecognized key: mcpServers",
}

FIX_SUGGESTIONS = {
    "Python.SyntaxError":      "Cek tanda kurung, titik dua, atau indentasi yang hilang/berlebihan.",
    "Python.IndentationError": "Pastikan konsistensi spasi/tab. Python sensitif terhadap indentasi.",
    "Python.NameError":        "Variabel/fungsi belum didefinisikan sebelum digunakan. Cek typo atau import.",
    "Python.TypeError":        "Tipe data tidak sesuai operasi. Gunakan type() atau isinstance() untuk debug.",
    "Python.AttributeError":   "Object tidak punya attribute itu. Cek typo, atau pastikan object bukan None.",
    "Python.ImportError":      "Module tidak tersedia. Coba: pip install <nama_module>",
    "Python.FileNotFound":     "File tidak ada di path yang ditentukan. Cek os.getcwd() dan relative path.",
    "Python.KeyError":         "Key tidak ada di dict. Gunakan dict.get(key) atau 'if key in dict:'.",
    "Python.IndexError":       "Index di luar range list. Cek len() sebelum akses index.",
    "Python.ValueError":       "Nilai tidak valid untuk operasi. Cek input dan konversi tipe data.",
    "Python.RuntimeError":     "Error saat runtime. Baca traceback lengkap untuk context lebih detail.",
    "Python.RecursionError":   "Stack overflow dari rekursi tak terbatas. Tambah base case atau pakai iterasi.",
    "Python.MemoryError":      "RAM habis. Kurangi ukuran data dalam memori atau proses secara batch.",
    "Python.PermissionError":  "Tidak ada izin akses file/direktori. Jalankan sebagai admin atau cek chmod.",
    "Python.TimeoutError":     "Operasi melebihi batas waktu. Tambah timeout atau optimasi operasi.",
    "Python.AssertionError":   "Assert statement gagal. Cek kondisi yang di-assert.",
    "Python.ZeroDivision":     "Pembagian dengan nol. Tambah pengecekan: if denominator != 0.",
    "Python.OSError":          "OS-level error. Bisa terkait file, network, atau proses.",
    "JS.TypeError":            "Tipe data salah di JavaScript. Cek apakah variable undefined/null sebelum akses.",
    "JS.ReferenceError":       "Variable belum dideklarasikan. Gunakan let/const/var yang benar.",
    "JS.SyntaxError":          "Syntax JS salah. Cek tanda kurung, koma, atau keyword yang salah.",
    "JS.ModuleNotFound":       "Module tidak ditemukan. Coba: npm install <module>",
    "JS.UnhandledRejection":   "Promise rejected tapi tidak di-catch. Tambah .catch() atau try/await.",
    "JS.ENOENT":               "File/folder tidak ada. Cek path dan pastikan file sudah dibuat.",
    "JS.EADDRINUSE":           "Port sudah dipakai. Ganti port atau kill process lain: lsof -i :PORT",
    "Rust.Panic":              "Runtime panic. Baca pesan panic untuk lokasi dan penyebabnya.",
    "Rust.CompileError":       "Compile error Rust. Baca kode error [Exxxx] di https://doc.rust-lang.org/error-index.html",
    "Rust.BorrowError":        "Borrow checker violation. Pastikan ownership dan lifetime sudah benar.",
    "Go.Panic":                "Goroutine panic. Baca stack trace untuk lokasi panic.",
    "Go.BuildError":           "Build error Go. Cek baris dan kolom yang ditunjuk di pesan error.",
    "HTTP.4xx":                "Client error. 400=bad request, 401=unauth, 403=forbidden, 404=not found.",
    "HTTP.5xx":                "Server error. Cek log server untuk detail internal error.",
    "DB.ConnectionError":      "Database tidak bisa dikoneksi. Pastikan DB running dan connection string benar.",
    "DB.Syntax":               "Query SQL salah. Cek syntax, tanda kutip, dan nama tabel/kolom.",
    "DB.UniqueViolation":      "Data duplikat melanggar UNIQUE constraint. Gunakan INSERT OR IGNORE atau upsert.",
    "DB.ForeignKey":           "Foreign key constraint violation. Pastikan data parent sudah ada.",
    "General.Timeout":         "Operasi timeout. Tambah batas waktu, optimalkan query, atau cek network.",
    "General.OOM":             "Out of memory. Kurangi penggunaan RAM, gunakan streaming, atau tambah RAM.",
    "General.SegFault":        "Segmentation fault. Cek akses memori null/invalid, biasa di C/C++/extension.",
    "General.Permission":      "Permission denied. Cek izin file (chmod) atau jalankan dengan hak lebih tinggi.",
    "General.NetworkError":    "Network error. Cek koneksi internet, firewall, dan apakah server up.",
    "MCP.Timeout":             "opencode MCP server startup timeout. Fix: 1) Wrap command with ['cmd', '/c', ...] di opencode.jsonc, 2) Set per-server timeout: 60000+ di config, 3) Lazy-load heavy imports in server code.",
    "MCP.RequestTimeout":      "MCP tool call timeout (tools/list terlalu lama). Fix: Per-server timeout 120000+ di opencode.jsonc, atau disable server jika tidak kritis.",
    "MCP.SpawnFailed":         "Config format salah (mcpServers vs mcp key). opencode v1.17+ pakai key 'mcp' bukan 'mcpServers'. Perbarui config ke schema baru.",
}

def _classify(text: str) -> list[str]:
    """Return list of matched error type strings."""
    found = []
    for etype, pattern in ERROR_PATTERNS.items():
        if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
            found.append(etype)
    return found if found else ["Unknown"]


def _parse_python_traceback(text: str) -> dict:
    """Extract structured info dari Python traceback."""
    result = {"language": "Python", "frames": [], "error_type": "", "error_message": ""}

    # Frame pattern: File "...", line N, in func
    frame_re = re.compile(
        r'File "([^"]+)", line (\d+)(?:, in (.+))?'
    )
    for m in frame_re.finditer(text):
        result["frames"].append({
            "file": m.group(1),
            "line": int(m.group(2)),
            "function": (m.group(3) or "").strip(),
        })

    # Final error line: ErrorType: message
    err_re = re.compile(r'^([A-Za-z]+(?:Error|Exception|Warning|Interrupt|Fault|Stop\w*))\s*:\s*(.+)$', re.MULTILINE)
    matches = list(err_re.finditer(text))
    if matches:
        last = matches[-1]
        result["error_type"] = last.group(1)
        result["error_message"] = last.group(2).strip()

    return result


def _parse_node_traceback(text: str) -> dict:
    """Extract structured info dari Node.js/JS stack trace."""
    result = {"language": "Node.js", "frames": [], "error_type": "", "error_message": ""}

    # First line biasanya: ErrorType: message
    first_line_re = re.compile(r'^(\w+Error(?:\s*\[.*?\])?)\s*:\s*(.+)$', re.MULTILINE)
    m = first_line_re.search(text)
    if m:
        result["error_type"] = m.group(1)
        result["error_message"] = m.group(2).strip()

    # Frame: at FuncName (file:line:col) atau at file:line:col
    frame_re = re.compile(r'at (?:(.+?) \()?([^():\s]+):(\d+):(\d+)\)?')
    for fm in frame_re.finditer(text):
        result["frames"].append({
            "function": (fm.group(1) or "anonymous").strip(),
            "file": fm.group(2),
            "line": int(fm.group(3)),
            "column": int(fm.group(4)),
        })

    return result


def _parse_rust_traceback(text: str) -> dict:
    """Extract structured info dari Rust panic / compile error."""
    result = {"language": "Rust", "frames": [], "error_type": "", "error_message": ""}

    # Rust 1.73+ (new format): thread 'main' panicked at src/main.rs:10:5: message
    # Rust pre-1.73 (old format): thread 'main' panicked at 'message', src/main.rs:10:5
    panic_re = re.compile(
        r"thread '(.+?)' panicked at "
        r"(?:'(.+?)', )?"                    # optional old-format message in quotes
        r"([^:']+):(\d+):(\d+)"              # file:line:col
        r"(?::\s*(.+))?"                     # optional new-format message after colon
    )
    m = panic_re.search(text)
    if m:
        result["error_type"] = "Panic"
        # Prefer new-format message (group 6), fallback to old-format (group 2)
        result["error_message"] = (m.group(6) or m.group(2) or "").strip()
        result["frames"].append({
            "thread": m.group(1),
            "file": m.group(3),
            "line": int(m.group(4)),
        })

    compile_re = re.compile(r'error\[(E\d+)\]: (.+)')
    for cm in compile_re.finditer(text):
        result["error_type"] = f"CompileError[{cm.group(1)}]"
        result["error_message"] = cm.group(2).strip()

    return result


def _auto_detect_language(text: str) -> str:
    """Detect language dari traceback text."""
    if "Traceback (most recent call last)" in text:
        return "python"
    if re.search(r'at \S+:\d+:\d+', text) and "Error:" in text:
        return "nodejs"
    if re.search(r"thread '.*' panicked(?: at)?|error\[E\d+\]", text):
        return "rust"
    if re.search(r'goroutine \d+ \[', text):
        return "go"
    return "unknown"


def _format_parsed(parsed: dict, raw_text: str) -> str:
    """Format parsed traceback menjadi teks yang mudah dibaca AI."""
    lang = parsed.get("language", "Unknown")
    etype = parsed.get("error_type", "Unknown")
    emsg = parsed.get("error_message", "")
    frames = parsed.get("frames", [])

    lines = [
        f"── Parsed {lang} Error ──────────────────────────",
        f"Type    : {etype}",
        f"Message : {emsg}",
    ]

    if frames:
        lines.append(f"Frames  : {len(frames)} stack frame(s)")
        # Show last 3 frames (most relevant)
        for fr in frames[-3:]:
            file_ = fr.get("file", "?")
            line_ = fr.get("line", "?")
            func_ = fr.get("function", "")
            lines.append(f"  → {file_}:{line_}" + (f" in {func_}" if func_ else ""))

    # Classifications
    classifications = _classify(raw_text)
    lines.append(f"Class   : {', '.join(classifications)}")

    # Suggestions
    suggestions = []
    for c in classifications:
        if c in FIX_SUGGESTIONS:
            suggestions.append(f"  [{c}] {FIX_SUGGESTIONS[c]}")
    if suggestions:
        lines.append("Fix Tips:")
        lines.extend(suggestions)

    return "\n".join(lines)


# ── Tools ────────────────────────────────────────────────────────────────────

@mcp.tool(
    name="parse_traceback",
    description=(
        "Parse Python / Node.js / Rust traceback string dan kembalikan info terstruktur: "
        "tipe error, pesan, stack frames, klasifikasi, dan saran fix. "
        "Gunakan ketika user paste atau AI menemukan traceback di output."
    ),
)
async def parse_traceback(
    traceback_text: str,
    language: str = "auto",
) -> str:
    """
    Args:
        traceback_text: String traceback / error output mentah
        language: "python" | "nodejs" | "rust" | "go" | "auto" (default)
    """
    if not traceback_text.strip():
        return "(empty input)"

    detected = language.lower()
    if detected == "auto":
        detected = _auto_detect_language(traceback_text)

    parsers = {
        "python": _parse_python_traceback,
        "nodejs": _parse_node_traceback,
        "node":   _parse_node_traceback,
        "rust":   _parse_rust_traceback,
    }

    parser = parsers.get(detected, _parse_python_traceback)
    parsed = parser(traceback_text)
    result = _format_parsed(parsed, traceback_text)

    _record(
        parsed.get("error_type", "Unknown"),
        parsed.get("error_message", traceback_text[:100]),
        f"parse_traceback ({detected})",
    )

    return result


@mcp.tool(
    name="read_log_tail",
    description=(
        "Baca N baris terakhir dari file log dan parse semua error di dalamnya. "
        "Berguna untuk melihat error terbaru dari log aplikasi, server, atau build."
    ),
)
async def read_log_tail(
    log_path: str,
    lines: int = 100,
    parse_errors: bool = True,
) -> str:
    """
    Args:
        log_path    : Path absolut atau relatif ke file log (.log, .txt, .err, dll)
        lines       : Jumlah baris terakhir yang dibaca (default: 100)
        parse_errors: Jika True, ekstrak dan klasifikasi semua error yang ditemukan
    """
    path = Path(log_path)
    if not path.exists():
        return f"(file not found: {log_path})"
    if not path.is_file():
        return f"(not a file: {log_path})"

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()

        tail = all_lines[-lines:] if len(all_lines) > lines else all_lines
        tail_text = "".join(tail)

        if not parse_errors:
            return f"[{log_path}] (last {len(tail)} lines):\n{tail_text}"

        # Find error lines
        error_line_re = re.compile(
            r'.*(ERROR|FATAL|CRITICAL|Exception|Traceback|panic|SIGSEGV'
            r'|Unhandled|Uncaught|FAILED|WARN).*',
            re.IGNORECASE,
        )
        error_lines = [(i + max(0, len(all_lines) - lines) + 1, l.rstrip())
                       for i, l in enumerate(tail)
                       if error_line_re.match(l)]

        result_parts = [
            f"── Log: {path.name} (last {len(tail)}/{len(all_lines)} lines) ──",
        ]

        if error_lines:
            result_parts.append(f"Found {len(error_lines)} error line(s):\n")
            for lineno, content in error_lines[:20]:
                classifications = _classify(content)
                result_parts.append(f"  Line {lineno:5d}: {content[:120]}")
                result_parts.append(f"           → {', '.join(classifications)}")
                _record(classifications[0], content[:200], f"{path.name}:{lineno}")
        else:
            result_parts.append("No obvious error lines found in this range.")

        result_parts.append(f"\n── Raw tail ──\n{tail_text[:3000]}")
        return "\n".join(result_parts)

    except Exception as e:
        return f"(error reading {log_path}: {e})"


@mcp.tool(
    name="watch_stderr",
    description=(
        "Jalankan command shell, tangkap stdout + stderr, parse error secara otomatis. "
        "Gunakan ketika ingin run script/test dan langsung dapat diagnosis errornya."
    ),
)
async def watch_stderr(
    command: str,
    workdir: str = "",
    timeout: int = 60,
) -> str:
    """
    Args:
        command : Command yang dijalankan (python script.py, npm run build, dll)
        workdir : Working directory (default: cwd)
        timeout : Maks detik tunggu (default: 60)
    """
    if not command.strip():
        return "(empty command)"

    # Safety: block shell injection dasar
    dangerous = ["rm -rf", "format ", "shutdown", "del /f", ":(){", ">("]
    for d in dangerous:
        if d.lower() in command.lower():
            return f"(blocked: command contains dangerous pattern '{d}')"

    cwd = workdir or os.getcwd()
    proc = None
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return f"(timeout after {timeout}s — process killed)"

        stdout = stdout_b.decode("utf-8", errors="replace")
        stderr = stderr_b.decode("utf-8", errors="replace")
        exit_code = proc.returncode

        parts = [
            f"── watch_stderr: {command!r} ──",
            f"Exit code : {exit_code}",
            f"CWD       : {cwd}",
        ]

        if stdout:
            parts.append(f"\n[stdout]\n{stdout[:3000]}")
        if stderr:
            parts.append(f"\n[stderr]\n{stderr[:3000]}")

        # Parse error dari stderr (dan stdout jika exit != 0)
        error_text = stderr + ("\n" + stdout if exit_code != 0 else "")
        if error_text.strip():
            lang = _auto_detect_language(error_text)
            parsers = {"python": _parse_python_traceback, "nodejs": _parse_node_traceback, "rust": _parse_rust_traceback}
            parsed = parsers.get(lang, _parse_python_traceback)(error_text)
            if parsed.get("error_type"):
                parts.append("\n" + _format_parsed(parsed, error_text))
                _record(parsed["error_type"], parsed.get("error_message", ""), f"watch_stderr:{command[:50]}")
            else:
                # Fallback: just classify
                classifications = _classify(error_text)
                if classifications != ["Unknown"]:
                    parts.append(f"\nError class: {', '.join(classifications)}")
                    for c in classifications:
                        if c in FIX_SUGGESTIONS:
                            parts.append(f"  [{c}] {FIX_SUGGESTIONS[c]}")
                    _record(classifications[0], error_text[:200], f"watch_stderr:{command[:50]}")

        return "\n".join(parts)

    except FileNotFoundError:
        return f"(command not found: {command.split()[0]})"
    except Exception as e:
        return f"(error running command: {e})"
    finally:
        if proc and proc.returncode is None:
            try:
                proc.kill()
            except Exception:
                pass


@mcp.tool(
    name="classify_error",
    description=(
        "Klasifikasi tipe error dari pesan error apapun (Python, JS, Rust, Go, HTTP, DB). "
        "Return tipe error + saran fix spesifik. "
        "Gunakan ketika hanya punya satu baris error message tanpa full traceback."
    ),
)
async def classify_error(error_message: str) -> str:
    """
    Args:
        error_message: Pesan error (satu baris atau lebih)
    """
    if not error_message.strip():
        return "(empty error message)"

    classifications = _classify(error_message)
    lines = [
        f"── Error Classification ──",
        f"Input   : {error_message[:200]}",
        f"Types   : {', '.join(classifications)}",
        "",
        "Fix Suggestions:",
    ]

    found_any = False
    for c in classifications:
        if c in FIX_SUGGESTIONS:
            lines.append(f"  [{c}]")
            lines.append(f"    {FIX_SUGGESTIONS[c]}")
            found_any = True

    if not found_any:
        lines.append("  Tidak ada saran spesifik. Cek dokumentasi atau search error message.")

    _record(classifications[0], error_message[:200], "classify_error")
    return "\n".join(lines)


@mcp.tool(
    name="scan_project_errors",
    description=(
        "Scan semua file .log, .err, stderr.txt dalam sebuah folder dan kumpulkan semua error. "
        "Berguna untuk audit error setelah build, deploy, atau test run."
    ),
)
async def scan_project_errors(
    folder_path: str,
    max_files: int = 20,
    lines_per_file: int = 50,
) -> str:
    """
    Args:
        folder_path   : Folder yang di-scan
        max_files     : Maks file yang dibaca (default: 20)
        lines_per_file: Maks baris per file (default: 50)
    """
    if not _is_path_allowed(folder_path):
        return f"(blocked: path not in allowlist: {folder_path})"
    folder = Path(folder_path)
    if not folder.exists():
        return f"(folder not found: {folder_path})"
    if not folder.is_dir():
        return f"(not a directory: {folder_path})"

    log_extensions = {".log", ".err", ".out", ".txt"}
    log_name_patterns = re.compile(r'(stderr|stdout|error|crash|debug|trace)', re.IGNORECASE)

    candidates = []
    for f in folder.rglob("*"):
        if f.is_file() and (f.suffix.lower() in log_extensions or log_name_patterns.search(f.name)):
            candidates.append(f)

    candidates.sort(key=lambda f: f.stat().st_mtime, reverse=True)  # newest first
    candidates = candidates[:max_files]

    if not candidates:
        return f"(no log/error files found in {folder_path})"

    summary_parts = [
        f"── Project Error Scan: {folder_path} ──",
        f"Found {len(candidates)} log file(s) to inspect:\n",
    ]

    total_errors = 0
    for f in candidates:
        try:
            with open(f, "r", encoding="utf-8", errors="replace") as fh:
                content_lines = fh.readlines()

            tail = content_lines[-lines_per_file:]
            tail_text = "".join(tail)

            error_line_re = re.compile(
                r'.*(ERROR|FATAL|CRITICAL|Exception|Traceback|panic|FAILED|Uncaught).*',
                re.IGNORECASE,
            )
            errs = [(i, l.rstrip()) for i, l in enumerate(tail) if error_line_re.match(l)]

            rel = f.relative_to(folder) if f.is_relative_to(folder) else f
            size_kb = f.stat().st_size // 1024
            mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")

            summary_parts.append(f"📄 {rel}  [{size_kb}KB, {mtime}]")
            if errs:
                total_errors += len(errs)
                for lineno, content in errs[:5]:
                    c = _classify(content)
                    summary_parts.append(f"   L{lineno+1}: {content[:100]}")
                    summary_parts.append(f"         → {', '.join(c)}")
                if len(errs) > 5:
                    summary_parts.append(f"   ... and {len(errs) - 5} more error line(s)")
            else:
                summary_parts.append("   (no obvious errors in last lines)")
            summary_parts.append("")

        except Exception as e:
            summary_parts.append(f"  {f.name}: (read error: {e})")

    summary_parts.append(f"── Total error lines found: {total_errors} ──")
    return "\n".join(summary_parts)


@mcp.tool(
    name="explain_error",
    description=(
        "Beri penjelasan mendalam + langkah-langkah fix untuk error type tertentu. "
        "Bisa dipakai setelah classify_error untuk mendapat panduan yang lebih detail."
    ),
)
async def explain_error(
    error_type: str,
    context: str = "",
) -> str:
    """
    Args:
        error_type: Tipe error (misal: 'Python.ImportError', 'JS.TypeError', dll)
                    Bisa juga tipe error langsung seperti 'ImportError' atau 'TypeError'.
        context   : Context tambahan (nama module, baris code, dll) untuk saran lebih spesifik
    """
    # Normalize: coba match langsung atau dengan prefix
    matched_key = None
    if error_type in FIX_SUGGESTIONS:
        matched_key = error_type
    else:
        # Fuzzy match
        et_lower = error_type.lower()
        for k in FIX_SUGGESTIONS:
            if et_lower in k.lower() or k.lower().endswith(et_lower):
                matched_key = k
                break

    lines = [f"── Error Explanation: {error_type} ──"]

    if matched_key:
        lines.append(f"Matched : {matched_key}")
        lines.append(f"\nFix Tip :\n  {FIX_SUGGESTIONS[matched_key]}")
    else:
        lines.append("(no specific explanation found for this error type)")
        lines.append(f"\nAvailable types:\n  " + "\n  ".join(sorted(FIX_SUGGESTIONS.keys())))

    # Context-aware additions
    if context:
        lines.append(f"\nContext yang diberikan:\n  {context[:300]}")

        if "import" in context.lower() and matched_key == "Python.ImportError":
            module_match = re.search(r"(?:import|from)\s+(\S+)", context)
            if module_match:
                mod = module_match.group(1).split(".")[0]
                lines.append(f"\n  Kemungkinan fix:\n    pip install {mod}")

        if re.search(r'\bNone\b|\bnull\b|\bundefined\b', context):
            lines.append("\n  ⚠️  Context mengandung None/null/undefined — cek apakah object sudah diinisialisasi.")

    lines.append("\n── Semua tipe error yang dikenali ──")
    by_lang: dict[str, list[str]] = {}
    for k in sorted(FIX_SUGGESTIONS.keys()):
        lang, _, name = k.partition(".")
        by_lang.setdefault(lang, []).append(name)
    for lang, names in by_lang.items():
        lines.append(f"  {lang}: {', '.join(names)}")

    return "\n".join(lines)


@mcp.tool(
    name="get_error_history",
    description=(
        "Tampilkan riwayat semua error yang sudah dibaca/di-parse di session ini. "
        "Berguna untuk lihat pola error yang berulang."
    ),
)
async def get_error_history(limit: int = 20) -> str:
    """
    Args:
        limit: Jumlah entry terakhir yang ditampilkan (default: 20)
    """
    if not _error_history:
        return "(no errors recorded in this session yet)"

    entries = _error_history[-limit:]
    lines = [f"── Error History (last {len(entries)}/{len(_error_history)}) ──\n"]

    for i, e in enumerate(reversed(entries), 1):
        lines.append(
            f"{i:2d}. [{e['timestamp'][11:19]}] {e['type']}\n"
            f"     Source : {e['source']}\n"
            f"     Message: {e['message'][:120]}\n"
        )

    # Error type frequency
    from collections import Counter
    freq = Counter(e["type"] for e in _error_history)
    lines.append("── Frequency ──")
    for etype, count in freq.most_common(5):
        lines.append(f"  {etype}: {count}x")

    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="stdio")
