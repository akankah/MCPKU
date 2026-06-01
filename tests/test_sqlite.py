import sys
sys.path.insert(0, r"E:\MCPKU")

import pytest
import tempfile
import os
from pathlib import Path
from mcp_sqlite import SqliteDB, _validate_identifier


class TestValidateIdentifier:
    def test_valid_simple(self):
        assert _validate_identifier("users") == '"users"'

    def test_valid_with_underscore(self):
        assert _validate_identifier("user_profiles") == '"user_profiles"'

    def test_valid_with_numbers(self):
        assert _validate_identifier("table1") == '"table1"'

    def test_valid_with_spaces(self):
        assert _validate_identifier("order items") == '"order items"'

    def test_invalid_semicolon(self):
        with pytest.raises(ValueError):
            _validate_identifier("users; DROP TABLE")

    def test_invalid_hyphen(self):
        with pytest.raises(ValueError):
            _validate_identifier("bad-table")

    def test_invalid_empty(self):
        with pytest.raises(ValueError):
            _validate_identifier("")

    def test_invalid_dot(self):
        with pytest.raises(ValueError):
            _validate_identifier("schema.table")

    def test_invalid_single_quote(self):
        with pytest.raises(ValueError):
            _validate_identifier("user's")


class TestSqliteDB:
    @pytest.fixture
    def db(self):
        tmp = Path(tempfile.mktemp(suffix=".db"))
        db = SqliteDB(str(tmp))
        yield db
        if tmp.exists():
            os.unlink(str(tmp))

    def test_create_table(self, db):
        result = db._execute_sync("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        assert len(result) == 1

    def test_insert_and_query(self, db):
        db._execute_sync("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        ins = db._execute_sync("INSERT INTO test VALUES (1, 'hello')")
        assert ins[0]["affected_rows"] == 1
        rows = db._execute_sync("SELECT * FROM test")
        assert len(rows) == 1
        assert rows[0]["name"] == "hello"

    def test_invalid_sql_raises(self, db):
        with pytest.raises(Exception):
            db._execute_sync("CREATE TABLE")

    def test_list_tables(self, db):
        db._execute_sync("CREATE TABLE test1 (id INTEGER)")
        db._execute_sync("CREATE TABLE test2 (id INTEGER)")
        rows = db._execute_sync("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        assert len(rows) == 2
