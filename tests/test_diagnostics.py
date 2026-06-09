import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from mcp_diagnostics import (
    _classify,
    _parse_python_traceback,
    _parse_node_traceback,
    _parse_rust_traceback,
    _auto_detect_language,
    _format_parsed,
    _record,
    _error_history,
    ERROR_PATTERNS,
)


@pytest.fixture(autouse=True)
def clear_history():
    _error_history.clear()


class TestClassify:
    def test_python_name_error(self):
        assert "Python.NameError" in _classify("NameError: name 'x' is not defined")

    def test_python_import_error(self):
        assert "Python.ImportError" in _classify("ModuleNotFoundError: No module named 'foo'")

    def test_python_syntax_error(self):
        assert "Python.SyntaxError" in _classify("SyntaxError: invalid syntax")

    def test_js_reference_error(self):
        assert "JS.ReferenceError" in _classify("ReferenceError: x is not defined")

    def test_js_module_not_found(self):
        assert "JS.ModuleNotFound" in _classify("Error: Cannot find module 'express'")

    def test_rust_panic(self):
        assert "Rust.Panic" in _classify("thread 'main' panicked at 'index out of bounds'")

    def test_rust_compile_error(self):
        assert "Rust.CompileError" in _classify("error[E0308]: mismatched types")

    def test_go_panic(self):
        assert "Go.Panic" in _classify("goroutine 1 [running]:")

    def test_db_connection_error(self):
        assert "DB.ConnectionError" in _classify("connection refused: database")

    def test_db_unique_violation(self):
        assert "DB.UniqueViolation" in _classify("duplicate key value violates unique constraint")

    def test_http_4xx(self):
        assert "HTTP.4xx" in _classify("404 error: not found")

    def test_http_5xx(self):
        assert "HTTP.5xx" in _classify("500 internal server error")

    def test_timeout(self):
        assert "General.Timeout" in _classify("timed out after 30 seconds")

    def test_oom(self):
        assert "General.OOM" in _classify("out of memory: killed by OOM killer")

    def test_segfault(self):
        assert "General.SegFault" in _classify("segmentation fault (core dumped)")

    def test_permission_denied(self):
        assert "General.Permission" in _classify("permission denied: access to path denied")

    def test_unknown_returns_unknown(self):
        assert _classify("foo bar baz qux") == ["Unknown"]

    def test_empty_string(self):
        assert _classify("") == ["Unknown"]


class TestAutoDetectLanguage:
    def test_python(self):
        assert _auto_detect_language("Traceback (most recent call last)\n  File \"x.py\", line 1") == "python"

    def test_nodejs(self):
        assert _auto_detect_language("TypeError: x is not a function\n    at file.js:10:5") == "nodejs"

    def test_rust_panic(self):
        assert _auto_detect_language("thread 'main' panicked at 'test'") == "rust"

    def test_rust_compile(self):
        assert _auto_detect_language("error[E0308]: mismatched types") == "rust"

    def test_go(self):
        assert _auto_detect_language("goroutine 1 [running]:") == "go"

    def test_unknown(self):
        assert _auto_detect_language("foo bar") == "unknown"

    def test_empty(self):
        assert _auto_detect_language("") == "unknown"


class TestParsePythonTraceback:
    def test_simple_traceback(self):
        tb = """Traceback (most recent call last):
  File "app.py", line 10, in <module>
    import pandas
ModuleNotFoundError: No module named 'pandas'"""
        result = _parse_python_traceback(tb)
        assert result["language"] == "Python"
        assert len(result["frames"]) == 1
        assert result["frames"][0]["file"] == "app.py"
        assert result["frames"][0]["line"] == 10
        assert result["error_type"] == "ModuleNotFoundError"
        assert "pandas" in result["error_message"]

    def test_multi_frame_traceback(self):
        tb = """Traceback (most recent call last):
  File "main.py", line 5, in <module>
    result = process_data()
  File "utils.py", line 20, in process_data
    return 1 / 0
ZeroDivisionError: division by zero"""
        result = _parse_python_traceback(tb)
        assert len(result["frames"]) == 2
        assert result["frames"][0]["function"] == "<module>"
        assert result["frames"][1]["function"] == "process_data"
        assert result["error_type"] == "ZeroDivisionError"

    def test_no_error(self):
        result = _parse_python_traceback("just some random text")
        assert result["error_type"] == ""
        assert result["error_message"] == ""

    def test_empty_string(self):
        result = _parse_python_traceback("")
        assert result["error_type"] == ""


class TestParseNodeTraceback:
    def test_node_traceback(self):
        tb = """TypeError: Cannot read property 'foo' of undefined
    at Object.<anonymous> (app.js:10:15)
    at Module._compile (module.js:653:30)"""
        result = _parse_node_traceback(tb)
        assert result["language"] == "Node.js"
        assert result["error_type"] == "TypeError"
        assert len(result["frames"]) == 2
        assert result["frames"][0]["file"] == "app.js"

    def test_no_error(self):
        result = _parse_node_traceback("no error here")
        assert result["error_type"] == ""


class TestParseRustTraceback:
    def test_rust_panic(self):
        tb = "thread 'main' panicked at 'index out of bounds: the len is 3', src/main.rs:10:5"
        result = _parse_rust_traceback(tb)
        assert result["language"] == "Rust"
        assert result["error_type"] == "Panic"
        assert result["frames"][0]["file"] == "src/main.rs"
        assert result["frames"][0]["line"] == 10

    def test_compile_error(self):
        tb = "error[E0308]: mismatched types\n --> src/lib.rs:5:15"
        result = _parse_rust_traceback(tb)
        assert "CompileError" in result["error_type"]

    def test_no_error(self):
        result = _parse_rust_traceback("just text")
        assert result["error_type"] == ""


class TestRecordHistory:
    def test_record_appends(self):
        assert len(_error_history) == 0
        _record("Python.NameError", "name 'x' is not defined", "test")
        assert len(_error_history) == 1
        assert _error_history[0]["type"] == "Python.NameError"

    def test_history_limit_100(self):
        for i in range(110):
            _record("Test.Error", f"error {i}", "")
        assert len(_error_history) <= 100


class TestFormatParsed:
    def test_format_includes_type_and_message(self):
        parsed = {"language": "Python", "frames": [], "error_type": "ValueError", "error_message": "bad value"}
        result = _format_parsed(parsed, "ValueError: bad value")
        assert "Python" in result
        assert "ValueError" in result
        assert "bad value" in result

    def test_format_includes_fix_tips(self):
        parsed = {"language": "Python", "frames": [], "error_type": "ImportError", "error_message": "No module"}
        result = _format_parsed(parsed, "ImportError")
        assert "pip install" in result


class TestErrorPatternsCoverage:
    def test_all_patterns_are_valid_regex(self):
        for name, pattern in ERROR_PATTERNS.items():
            import re
            try:
                re.compile(pattern)
            except re.error as e:
                pytest.fail(f"Invalid regex in {name}: {e}")
