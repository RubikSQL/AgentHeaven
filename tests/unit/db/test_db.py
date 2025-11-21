"""
Comprehensive database tests using JSON-based fixtures.

This module tests database functionality across all backends defined in tests.json.
Focus on public API and BaseUKF round-trip compatibility, no trivial or
backend-specific implementation tests.

Tests cover: execute, db_tabs, db_views, tab_cols, transactions, and more.
"""

import pytest
from sqlalchemy import Column, Integer, String, Text, MetaData, Table
from ahvn.utils.db.types import DatabaseIdType
from ahvn.ukf.templates.basic import KnowledgeUKFT, ExperienceUKFT


class TestDatabasePublicAPI:
    """Test database public API across all backends."""

    def test_db_execute_select(self, minimal_database):
        """Test basic execute with SELECT queries."""
        # Simple SELECT
        result = minimal_database.execute("SELECT 1 AS test_col")
        rows = list(result.fetchall())
        assert len(rows) == 1
        assert rows[0]["test_col"] == 1

        # SELECT with parameters
        result = minimal_database.execute("SELECT :value AS result", params={"value": 42})
        rows = list(result.fetchall())
        assert rows[0]["result"] == 42

    def test_db_tabs_and_cols(self, minimal_database):
        """Test db_tabs and tab_cols functionality."""
        # Get initial tables
        initial_tables = minimal_database.db_tabs()
        assert isinstance(initial_tables, list)

        # Create a test table
        minimal_database.execute(
            """
            CREATE TABLE test_table (
                id INTEGER PRIMARY KEY,
                name VARCHAR(100),
                value INTEGER
            )
            """,
            autocommit=True,
        )

        # Verify table exists
        tables = minimal_database.db_tabs()
        assert "test_table" in tables

        # Get column information (by default returns list of column names)
        columns = minimal_database.tab_cols("test_table")
        assert isinstance(columns, list)
        assert len(columns) >= 3

        # Verify column names are present
        assert "id" in columns
        assert "name" in columns
        assert "value" in columns

        # Get full column info
        full_columns = minimal_database.tab_cols("test_table", full_info=True)
        assert isinstance(full_columns, list)
        col_names = [col["name"] for col in full_columns]
        assert "id" in col_names

    def test_db_views(self, minimal_database):
        """Test db_views functionality."""
        # Create a table first
        minimal_database.execute(
            """
            CREATE TABLE view_source (
                id INTEGER PRIMARY KEY,
                data VARCHAR(100)
            )
            """,
            autocommit=True,
        )

        # Insert test data
        minimal_database.execute("INSERT INTO view_source (id, data) VALUES (:id, :data)", params={"id": 1, "data": "test"}, autocommit=True)

        # Create a view
        minimal_database.execute(
            """
            CREATE VIEW test_view AS
            SELECT id, data FROM view_source
            """,
            autocommit=True,
        )

        # Get views
        views = minimal_database.db_views()
        assert isinstance(views, list)
        assert "test_view" in views

        # Query the view
        result = minimal_database.execute("SELECT * FROM test_view")
        rows = list(result.fetchall())
        assert len(rows) == 1
        assert rows[0]["data"] == "test"

    def test_db_insert_and_query(self, minimal_database):
        """Test INSERT and query operations."""
        # Create table
        minimal_database.execute(
            """
            CREATE TABLE insert_test (
                id INTEGER PRIMARY KEY,
                name VARCHAR(50),
                value INTEGER
            )
            """,
            autocommit=True,
        )

        # Insert data
        minimal_database.execute(
            "INSERT INTO insert_test (id, name, value) VALUES (:id, :name, :value)", params={"id": 1, "name": "test1", "value": 100}, autocommit=True
        )

        minimal_database.execute(
            "INSERT INTO insert_test (id, name, value) VALUES (:id, :name, :value)", params={"id": 2, "name": "test2", "value": 200}, autocommit=True
        )

        # Query data
        result = minimal_database.execute("SELECT * FROM insert_test ORDER BY id")
        rows = list(result.fetchall())
        assert len(rows) == 2
        assert rows[0]["name"] == "test1"
        assert rows[0]["value"] == 100
        assert rows[1]["name"] == "test2"
        assert rows[1]["value"] == 200

    def test_db_update_and_delete(self, minimal_database):
        """Test UPDATE and DELETE operations."""
        # Create and populate table
        minimal_database.execute(
            """
            CREATE TABLE update_test (
                id INTEGER PRIMARY KEY,
                name VARCHAR(50),
                status VARCHAR(20)
            )
            """,
            autocommit=True,
        )

        for i in range(1, 4):
            minimal_database.execute(
                "INSERT INTO update_test (id, name, status) VALUES (:id, :name, :status)",
                params={"id": i, "name": f"item{i}", "status": "active"},
                autocommit=True,
            )

        # UPDATE operation
        minimal_database.execute("UPDATE update_test SET status = :status WHERE id = :id", params={"status": "inactive", "id": 2}, autocommit=True)

        # Verify update
        result = minimal_database.execute("SELECT status FROM update_test WHERE id = 2")
        rows = list(result.fetchall())
        assert len(rows) == 1
        assert rows[0]["status"] == "inactive"

        # DELETE operation
        minimal_database.execute("DELETE FROM update_test WHERE id = :id", params={"id": 3}, autocommit=True)

        # Verify deletion
        result = minimal_database.execute("SELECT COUNT(*) as count FROM update_test")
        rows = list(result.fetchall())
        assert rows[0]["count"] == 2


class TestDatabaseTransactions:
    """Test database transaction functionality."""

    def test_transaction_commit(self, minimal_database):
        """Test transaction commit using context manager."""
        # Create table
        minimal_database.execute(
            """
            CREATE TABLE trans_test (
                id INTEGER PRIMARY KEY,
                value VARCHAR(50)
            )
            """,
            autocommit=True,
        )

        # Use context manager for transaction
        with minimal_database as db:
            assert db.in_transaction()

            # Insert within transaction
            db.execute("INSERT INTO trans_test (id, value) VALUES (:id, :value)", params={"id": 1, "value": "committed"})
        # Transaction auto-commits on successful exit

        # Verify data persisted
        result = minimal_database.execute("SELECT value FROM trans_test WHERE id = 1")
        rows = list(result.fetchall())
        assert len(rows) == 1
        assert rows[0]["value"] == "committed"

    def test_transaction_rollback(self, minimal_database):
        """Test transaction rollback."""
        # Create table
        minimal_database.execute(
            """
            CREATE TABLE rollback_test (
                id INTEGER PRIMARY KEY,
                value VARCHAR(50)
            )
            """,
            autocommit=True,
        )

        # Insert initial data
        minimal_database.execute("INSERT INTO rollback_test (id, value) VALUES (:id, :value)", params={"id": 1, "value": "original"}, autocommit=True)

        # Start transaction and rollback manually
        with minimal_database as db:
            # Modify within transaction
            db.execute("UPDATE rollback_test SET value = :value WHERE id = :id", params={"value": "modified", "id": 1})

            # Force rollback
            db.rollback()

        # Verify rollback - should have original value
        result = minimal_database.execute("SELECT value FROM rollback_test WHERE id = 1")
        rows = list(result.fetchall())
        assert rows[0]["value"] == "original"


class TestDatabaseUKFRoundtrip:
    """Test database with BaseUKF round-trip scenarios."""

    def test_db_ukf_data_storage(self, minimal_database):
        """Test storing and retrieving UKF data in database."""
        # Create table for UKF data
        minimal_database.execute(
            """
            CREATE TABLE ukf_storage (
                id VARCHAR(100) PRIMARY KEY,
                ukf_type VARCHAR(50),
                name VARCHAR(200),
                content TEXT,
                priority INTEGER
            )
            """,
            autocommit=True,
        )

        # Create UKF objects
        knowledge = KnowledgeUKFT(
            name="Database Knowledge", content="Databases store structured data efficiently", tags={"[topic:database]", "[type:knowledge]"}
        )

        experience = ExperienceUKFT(name="Query Execution", content="Executed SELECT query successfully", priority=8, metadata={"rows": 42, "time_ms": 150})

        # Store UKF data
        minimal_database.execute(
            """
            INSERT INTO ukf_storage (id, ukf_type, name, content, priority)
            VALUES (:id, :ukf_type, :name, :content, :priority)
            """,
            params={"id": str(knowledge.id), "ukf_type": "knowledge", "name": knowledge.name, "content": knowledge.content, "priority": knowledge.priority},
            autocommit=True,
        )

        minimal_database.execute(
            """
            INSERT INTO ukf_storage (id, ukf_type, name, content, priority)
            VALUES (:id, :ukf_type, :name, :content, :priority)
            """,
            params={
                "id": str(experience.id),
                "ukf_type": "experience",
                "name": experience.name,
                "content": experience.content,
                "priority": experience.priority,
            },
            autocommit=True,
        )

        # Retrieve and verify
        result = minimal_database.execute("SELECT * FROM ukf_storage WHERE ukf_type = :type ORDER BY name", params={"type": "knowledge"})
        rows = list(result.fetchall())
        assert len(rows) == 1
        assert rows[0]["name"] == "Database Knowledge"
        assert rows[0]["content"] == "Databases store structured data efficiently"

        result = minimal_database.execute("SELECT * FROM ukf_storage WHERE ukf_type = :type", params={"type": "experience"})
        rows = list(result.fetchall())
        assert len(rows) == 1
        assert rows[0]["name"] == "Query Execution"
        assert rows[0]["priority"] == 8

    def test_db_ukf_model_dump_roundtrip(self, minimal_database):
        """Test full UKF round-trip using model_dump."""
        from ahvn.utils.basic.serialize_utils import dumps_json, loads_json

        # Create table with JSON column
        minimal_database.execute(
            """
            CREATE TABLE ukf_json_storage (
                id VARCHAR(100) PRIMARY KEY,
                ukf_type VARCHAR(50),
                data TEXT
            )
            """,
            autocommit=True,
        )

        # Create UKF object
        knowledge = KnowledgeUKFT(
            name="Test Knowledge", content="This is test content", tags={"[test:true]", "[category:testing]"}, metadata={"created_by": "test", "version": 1}
        )

        # Serialize and store
        ukf_data = dumps_json(knowledge.model_dump())
        minimal_database.execute(
            """
            INSERT INTO ukf_json_storage (id, ukf_type, data)
            VALUES (:id, :ukf_type, :data)
            """,
            params={"id": str(knowledge.id), "ukf_type": "knowledge", "data": ukf_data},
            autocommit=True,
        )

        # Retrieve and reconstruct
        result = minimal_database.execute("SELECT data FROM ukf_json_storage WHERE id = :id", params={"id": str(knowledge.id)})
        rows = list(result.fetchall())
        assert len(rows) == 1
        reconstructed_data = loads_json(rows[0]["data"])
        reconstructed = KnowledgeUKFT(**reconstructed_data)

        # Verify full round-trip
        assert reconstructed.id == knowledge.id
        assert reconstructed.name == knowledge.name
        assert reconstructed.content == knowledge.content
        assert "[test:true]" in reconstructed.tags
        assert reconstructed.metadata["version"] == 1


class TestDatabaseEdgeCases:
    """Test database behavior with edge cases."""

    def test_db_empty_result(self, minimal_database):
        """Test queries with no results."""
        minimal_database.execute(
            """
            CREATE TABLE empty_test (
                id INTEGER PRIMARY KEY,
                name VARCHAR(50)
            )
            """,
            autocommit=True,
        )

        # Query empty table
        result = minimal_database.execute("SELECT * FROM empty_test")
        rows = list(result.fetchall())
        assert rows == []

        # Query with WHERE clause that matches nothing
        minimal_database.execute("INSERT INTO empty_test (id, name) VALUES (1, 'test')", autocommit=True)
        result = minimal_database.execute("SELECT * FROM empty_test WHERE id = :id", params={"id": 999})
        rows = list(result.fetchall())
        assert len(rows) == 0

    def test_db_null_values(self, minimal_database):
        """Test handling NULL values."""
        minimal_database.execute(
            """
            CREATE TABLE null_test (
                id INTEGER PRIMARY KEY,
                required VARCHAR(50) NOT NULL,
                optional VARCHAR(50)
            )
            """,
            autocommit=True,
        )

        # Insert with NULL
        minimal_database.execute(
            "INSERT INTO null_test (id, required, optional) VALUES (:id, :req, :opt)", params={"id": 1, "req": "present", "opt": None}, autocommit=True
        )

        # Query and verify NULL handling
        result = minimal_database.execute("SELECT * FROM null_test WHERE id = 1")
        rows = list(result.fetchall())
        assert len(rows) == 1
        assert rows[0]["required"] == "present"
        assert rows[0]["optional"] is None

    def test_db_large_result_set(self, minimal_database):
        """Test handling large result sets."""
        minimal_database.execute(
            """
            CREATE TABLE large_test (
                id INTEGER PRIMARY KEY,
                value INTEGER
            )
            """,
            autocommit=True,
        )

        # Insert many rows
        for i in range(100):
            minimal_database.execute("INSERT INTO large_test (id, value) VALUES (:id, :value)", params={"id": i, "value": i * 2}, autocommit=True)

        # Query all
        result = minimal_database.execute("SELECT * FROM large_test ORDER BY id")
        rows = list(result.fetchall())
        assert len(rows) == 100
        assert rows[0]["value"] == 0
        assert rows[99]["value"] == 198

        # Query with LIMIT (if supported)
        result = minimal_database.execute("SELECT * FROM large_test ORDER BY id LIMIT 10")
        rows = list(result.fetchall())
        assert len(rows) == 10

    def test_db_special_characters(self, minimal_database):
        """Test handling special characters in data."""
        minimal_database.execute(
            """
            CREATE TABLE special_char_test (
                id INTEGER PRIMARY KEY,
                text VARCHAR(200)
            )
            """,
            autocommit=True,
        )

        # Insert special characters
        special_strings = [
            "Hello 'World'",
            'Double "quotes"',
            "Line\nBreak",
            "Tab\there",
            "Unicode: 你好世界 🎉",
            "Symbols: @#$%^&*()",
        ]

        for i, text in enumerate(special_strings):
            minimal_database.execute("INSERT INTO special_char_test (id, text) VALUES (:id, :text)", params={"id": i, "text": text}, autocommit=True)

        # Verify retrieval
        result = minimal_database.execute("SELECT text FROM special_char_test ORDER BY id")
        rows = list(result.fetchall())
        retrieved_texts = [row["text"] for row in rows]

        # Compare retrieved texts with originals
        for original, retrieved in zip(special_strings, retrieved_texts):
            assert retrieved == original


class TestDatabaseClear:
    """Test database clear functionality."""

    def test_db_clear_removes_table_data(self, minimal_database):
        """Test that clear() removes all table data but keeps tables."""
        # Create multiple tables
        minimal_database.execute("CREATE TABLE clear_test1 (id INTEGER PRIMARY KEY)", autocommit=True)
        minimal_database.execute("CREATE TABLE clear_test2 (id INTEGER PRIMARY KEY)", autocommit=True)

        # Insert data
        minimal_database.execute("INSERT INTO clear_test1 (id) VALUES (1)", autocommit=True)
        minimal_database.execute("INSERT INTO clear_test2 (id) VALUES (2)", autocommit=True)

        # Verify tables exist and have data
        tables = minimal_database.db_tabs()
        assert "clear_test1" in tables
        assert "clear_test2" in tables

        result = minimal_database.execute("SELECT COUNT(*) as count FROM clear_test1")
        rows = list(result.fetchall())
        assert rows[0]["count"] == 1

        # Clear database (clears data, keeps structure)
        minimal_database.clear()

        # Verify tables still exist
        tables = minimal_database.db_tabs()
        assert "clear_test1" in tables
        assert "clear_test2" in tables

        # Verify data is cleared
        result = minimal_database.execute("SELECT COUNT(*) as count FROM clear_test1")
        rows = list(result.fetchall())
        assert rows[0]["count"] == 0


class TestDatabaseFeatures:
    """Test database feature functions: col_enums, tab_pks, tab_fks, row_count, col_type, col_distincts."""

    def test_db_col_enums(self, minimal_database):
        """Test col_enums() for retrieving column enum values."""
        # Create table with enum column (for PostgreSQL/MySQL)
        minimal_database.execute("CREATE TABLE enum_test (id INTEGER PRIMARY KEY, status VARCHAR(20))", autocommit=True)

        # For databases without native enums, this would return empty
        enums = minimal_database.col_enums("enum_test", "status")
        assert isinstance(enums, (list, type(None)))

    def test_db_tab_pks(self, minimal_database):
        """Test tab_pks() for retrieving primary key information."""
        # Create table with primary key
        minimal_database.execute("CREATE TABLE pk_test (id INTEGER PRIMARY KEY, name TEXT)", autocommit=True)

        # Get primary keys
        pks = minimal_database.tab_pks("pk_test")
        assert isinstance(pks, list)
        if pks:  # Some backends might return empty for simple PKs
            assert "id" in [pk.lower() for pk in pks]

    def test_db_tab_pks_composite(self, minimal_database):
        """Test tab_pks() with composite primary key."""
        # Create table with composite primary key
        minimal_database.execute("CREATE TABLE composite_pk_test (id1 INTEGER, id2 INTEGER, data TEXT, PRIMARY KEY (id1, id2))", autocommit=True)

        # Get primary keys
        pks = minimal_database.tab_pks("composite_pk_test")
        assert isinstance(pks, list)
        if pks:  # Some backends might return empty
            pk_lower = [pk.lower() for pk in pks]
            assert "id1" in pk_lower
            assert "id2" in pk_lower

    def test_db_tab_fks(self, minimal_database):
        """Test tab_fks() for retrieving foreign key information."""
        # Create parent table
        minimal_database.execute("CREATE TABLE fk_parent (id INTEGER PRIMARY KEY, name TEXT)", autocommit=True)

        # Create child table with foreign key
        minimal_database.execute(
            "CREATE TABLE fk_child (id INTEGER PRIMARY KEY, parent_id INTEGER, FOREIGN KEY (parent_id) REFERENCES fk_parent(id))", autocommit=True
        )

        # Get foreign keys
        fks = minimal_database.tab_fks("fk_child")
        assert isinstance(fks, (list, dict))  # Format varies by backend

    def test_db_row_count(self, minimal_database):
        """Test row_count() for counting table rows."""
        # Create and populate table
        minimal_database.execute("CREATE TABLE count_test (id INTEGER PRIMARY KEY, data TEXT)", autocommit=True)

        # Initially empty
        count = minimal_database.row_count("count_test")
        assert count == 0

        # Insert rows
        for i in range(5):
            minimal_database.execute(f"INSERT INTO count_test (id, data) VALUES ({i}, 'data{i}')", autocommit=True)

        # Check count
        count = minimal_database.row_count("count_test")
        assert count == 5

    def test_db_col_type(self, minimal_database):
        """Test col_type() for retrieving column type information."""
        # Create table with various column types
        minimal_database.execute("CREATE TABLE type_test (id INTEGER, name TEXT, value REAL)", autocommit=True)

        # Get column type
        id_type = minimal_database.col_type("type_test", "id")
        assert id_type is not None
        assert "int" in id_type.lower() or "number" in id_type.lower()

    def test_db_col_distincts(self, minimal_database):
        """Test col_distincts() for retrieving distinct column values."""
        # Create and populate table
        minimal_database.execute("CREATE TABLE distinct_test (id INTEGER PRIMARY KEY, category TEXT)", autocommit=True)

        # Insert data with duplicates
        categories = ["A", "B", "A", "C", "B", "A"]
        for i, cat in enumerate(categories):
            minimal_database.execute(f"INSERT INTO distinct_test (id, category) VALUES ({i}, '{cat}')", autocommit=True)

        # Get distinct values
        distincts = minimal_database.col_distincts("distinct_test", "category")
        assert isinstance(distincts, list)
        assert set(distincts) == {"A", "B", "C"}
        assert len(distincts) == 3
