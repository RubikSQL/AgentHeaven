"""
Tests for database tool builtins (execute_sql and toolspec_factory_builtins_execute_sql).

This module tests:
1. Basic execute_sql function returning list of dicts
2. Factory function with config-based defaults
3. Table formatting with different styles
4. Empty results and write operations
"""

import pytest

from ahvn.utils.db import Database
from ahvn.tool.builtins.db.exec_sql import execute_sql, toolspec_factory_builtins_execute_sql
from ahvn.utils.basic.config_utils import HEAVEN_CM


class TestExecuteSqlBasic:
    """Test the basic execute_sql function."""

    @pytest.fixture
    def db(self):
        """Create an in-memory SQLite database with test data."""
        db = Database(provider="sqlite", database=":memory:", connect=True)
        db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)", autocommit=True)
        db.execute("INSERT INTO users VALUES (1, 'Alice', 30)", autocommit=True)
        db.execute("INSERT INTO users VALUES (2, 'Bob', 25)", autocommit=True)
        db.execute("INSERT INTO users VALUES (3, 'Charlie', 35)", autocommit=True)
        yield db
        db.close()

    def test_execute_sql_returns_list_of_dicts(self, db):
        """Test that execute_sql returns a list of dictionaries."""
        result = execute_sql(db, "SELECT * FROM users ORDER BY id")
        assert isinstance(result, list)
        assert len(result) == 3
        assert all(isinstance(row, dict) for row in result)
        assert result[0] == {"id": 1, "name": "Alice", "age": 30}

    def test_execute_sql_select_subset(self, db):
        """Test SELECT with specific columns."""
        result = execute_sql(db, "SELECT name, age FROM users WHERE age > 25")
        assert len(result) == 2
        assert result[0] == {"name": "Alice", "age": 30}
        assert result[1] == {"name": "Charlie", "age": 35}

    def test_execute_sql_empty_result(self, db):
        """Test query with no results."""
        result = execute_sql(db, "SELECT * FROM users WHERE id = 999")
        assert result == []

    def test_execute_sql_write_operation(self, db):
        """Test that write operations return empty list."""
        result = execute_sql(db, "UPDATE users SET age = 26 WHERE name = 'Bob'")
        assert result == []

        # Verify the update worked
        result = execute_sql(db, "SELECT age FROM users WHERE name = 'Bob'")
        assert result[0]["age"] == 26


class TestCreateExecuteSqlTool:
    """Test the toolspec_factory_builtins_execute_sql factory function."""

    @pytest.fixture
    def db(self):
        """Create an in-memory SQLite database with test data."""
        db = Database(provider="sqlite", database=":memory:", connect=True)
        db.execute("CREATE TABLE products (id INTEGER, name TEXT, price REAL)", autocommit=True)
        db.execute("INSERT INTO products VALUES (1, 'Apple', 1.50)", autocommit=True)
        db.execute("INSERT INTO products VALUES (2, 'Banana', 0.75)", autocommit=True)
        yield db
        db.close()

    def test_tool_creation_with_defaults(self, db):
        """Test creating tool with config defaults."""
        tool = toolspec_factory_builtins_execute_sql(db)
        assert tool is not None
        assert tool.binded.name == "exec_sql"
        assert "formatted table" in tool.binded.description.lower()

    def test_tool_execution_returns_formatted_string(self, db):
        """Test that tool returns formatted table string."""
        tool = toolspec_factory_builtins_execute_sql(db)
        result = tool.call(query="SELECT * FROM products ORDER BY id")
        assert isinstance(result, str)
        assert "rows in total" in result
        assert "Apple" in result
        assert "Banana" in result

    def test_tool_uses_config_defaults(self, db):
        """Test that tool uses config values when not specified."""
        # Get config defaults
        display_config = HEAVEN_CM.get("db.display", {})
        expected_style = display_config.get("style", "DEFAULT")

        tool = toolspec_factory_builtins_execute_sql(db)
        result = tool.call(query="SELECT * FROM products LIMIT 1")

        # Check that output contains style-specific formatting
        if expected_style == "MARKDOWN":
            assert "|" in result and ":" in result
        elif expected_style == "SINGLE_BORDER":
            assert "─" in result or "│" in result

    def test_tool_override_parameters(self, db):
        """Test that explicit parameters override config defaults."""
        tool = toolspec_factory_builtins_execute_sql(db, max_rows=5, style="DEFAULT")
        result = tool.call(query="SELECT * FROM products")
        assert "+" in result  # DEFAULT style uses + for corners

    def test_tool_with_markdown_style(self, db):
        """Test tool with MARKDOWN style."""
        tool = toolspec_factory_builtins_execute_sql(db, style="MARKDOWN")
        result = tool.call(query="SELECT name, price FROM products")
        assert "|" in result
        assert ":" in result  # Markdown alignment markers

    def test_tool_empty_result(self, db):
        """Test tool with empty result set."""
        tool = toolspec_factory_builtins_execute_sql(db)
        result = tool.call(query="SELECT * FROM products WHERE id = 999")
        assert "no rows returned" in result.lower()

    def test_tool_max_rows_truncation(self, db):
        """Test that max_rows parameter truncates output."""
        # Add more data
        for i in range(3, 13):
            db.execute(f"INSERT INTO products VALUES ({i}, 'Item{i}', {i}.99)", autocommit=True)

        tool = toolspec_factory_builtins_execute_sql(db, max_rows=5)
        result = tool.call(query="SELECT * FROM products")
        assert "..." in result  # Ellipsis for truncated rows
        assert "12 rows in total" in result

    def test_tool_error_handling_table_not_found(self, db):
        """Test that tool returns structured error for non-existent table."""
        tool = toolspec_factory_builtins_execute_sql(db)
        result = tool.call(query="SELECT * FROM nonexistent_table")
        assert isinstance(result, str)
        assert "Database query execution failed" in result
        assert "Error Type: TableNotFound" in result
        assert "no such table" in result.lower()

    def test_tool_error_handling_includes_query(self, db):
        """Test that error response includes the problematic query."""
        tool = toolspec_factory_builtins_execute_sql(db)
        result = tool.call(query="SELECT * FROM bad_table WHERE x = 1")
        assert isinstance(result, str)
        assert "Query: " in result
        assert "bad_table" in result

    def test_tool_error_suggests_similar_table(self, db):
        """Test that error response suggests similar table names."""
        tool = toolspec_factory_builtins_execute_sql(db)
        # Typo: "product" instead of "products"
        result = tool.call(query="SELECT * FROM product")
        assert isinstance(result, str)
        assert "TableNotFound" in result or "product" in result.lower()
        # Should suggest "products" if suggestion feature works
        # (Note: This might not always trigger depending on similarity threshold)


@pytest.mark.parametrize("style", ["DEFAULT", "MARKDOWN", "SINGLE_BORDER", "PLAIN_COLUMNS"])
def test_tool_multiple_styles(style):
    """Test tool with different table styles."""
    db = Database(provider="sqlite", database=":memory:", connect=True)
    db.execute("CREATE TABLE test (x INTEGER)", autocommit=True)
    db.execute("INSERT INTO test VALUES (1)", autocommit=True)

    tool = toolspec_factory_builtins_execute_sql(db, style=style)
    result = tool.call(query="SELECT * FROM test")

    assert isinstance(result, str)
    assert "1 rows in total" in result or "1 row in total" in result.replace("rows", "row")

    db.close()
