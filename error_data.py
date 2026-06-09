"""Shared error data: FIX_SUGGESTIONS and FIX_STRATEGIES_DESC.

Central source of truth to avoid duplication between mcp_autofix.py
and mcp_diagnostics.py (Indonesian variant kept in diagnostics).
"""

FIX_SUGGESTIONS = {
    "Python.ImportError": "Missing Python package. Use pip install <package>.",
    "Python.ModuleNotFoundError": "Missing Python module. Use pip install <package>.",
    "Python.SyntaxError": "Check for missing brackets, colons, or indentation.",
    "Python.IndentationError": "Fix indentation — mix of tabs/spaces.",
    "Python.NameError": "Check variable/function name for typos.",
    "Python.TypeError": "Check types — use type() or isinstance().",
    "Python.AttributeError": "Check attribute name or None object.",
    "Python.FileNotFound": "Check file path and current working directory.",
    "Python.KeyError": "Use dict.get(key) instead of dict[key].",
    "Python.IndexError": "Check list length before accessing index.",
    "Python.ValueError": "Check input value and type conversion.",
    "Python.RuntimeError": "Generic runtime error — read full traceback.",
    "Python.RecursionError": "Add base case or switch to iteration.",
    "Python.MemoryError": "Reduce data in memory or process in batches.",
    "Python.PermissionError": "Run as admin or check file permissions.",
    "Python.TimeoutError": "Increase timeout or optimize operation.",
    "Python.AssertionError": "Check asserted condition.",
    "Python.ZeroDivision": "Add denominator check.",
    "JS.ModuleNotFound": "Missing npm package. Use npm install <module>.",
    "JS.ReferenceError": "Check variable declaration (let/const/var).",
    "JS.TypeError": "Check for undefined/null before access.",
    "JS.SyntaxError": "Check brackets, commas, or keywords.",
    "JS.UnhandledRejection": "Add .catch() or async/await try block.",
    "JS.ENOENT": "Check file path.",
    "JS.EACCES": "Check permissions.",
    "JS.EADDRINUSE": "Change port or kill existing process.",
    "Rust.Panic": "Read panic message for location and cause.",
    "Rust.CompileError": "Check error code at doc.rust-lang.org.",
    "Rust.BorrowError": "Fix ownership and lifetimes.",
    "Go.Panic": "Read stack trace for panic location.",
    "Go.BuildError": "Check line/column in error message.",
    "DB.ConnectionError": "Ensure DB is running and connection string is correct.",
    "DB.Syntax": "Check SQL syntax and quotes.",
    "DB.UniqueViolation": "Use INSERT OR IGNORE or upsert.",
    "DB.ForeignKey": "Ensure parent data exists.",
    "General.Timeout": "Increase timeout, optimize, or check network.",
    "General.OOM": "Reduce RAM usage or use streaming.",
    "General.SegFault": "Check null/invalid memory access.",
    "General.Permission": "Check permissions or run with higher privileges.",
    "General.NetworkError": "Check internet, firewall, and server status.",
}

FIX_STRATEGIES_DESC = {
    "Python.ImportError": "pip install <package> (auto-extract)",
    "Python.ModuleNotFoundError": "pip install <package> (auto-extract)",
    "JS.ModuleNotFound": "npm install <package> (auto-extract)",
    "Python.FileNotFound": "mkdir parent directory (auto-extract path)",
    "JS.ENOENT": "mkdir parent directory (auto-extract path)",
    "JS.EADDRINUSE": "netstat + taskkill / lsof -ti:PORT | kill (auto-extract port)",
    "Go.BuildError": "go mod tidy",
    "Python.IndentationError": "black <file> (auto-extract file from traceback)",
}
