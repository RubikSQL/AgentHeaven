"""Tests for SQL compiler with NF operator and nested operators."""

import pytest
from ahvn.adapter.db import ORMUKFAdapter
from ahvn.utils.db.compiler import SQLCompiler
from ahvn.utils.klop import KLOp


class TestSQLCompilerNF:
    """Test SQL compiler's handling of NF operator with nested operators."""

    @pytest.fixture
    def adapter(self):
        """Create ORMUKFAdapter with tags field (NF type)."""
        return ORMUKFAdapter(name="test_nf")

    def test_nf_basic(self, adapter):
        """Test basic NF operator without nested operators."""
        # NF(slot="TOPIC", value_="math")
        nf_expr = KLOp.NF(slot="TOPIC", value_="math")
        expr = KLOp.expr(tags=nf_expr)

        # Compile to SQL
        clause = SQLCompiler.compile(orms=adapter.dims, expr=expr)

        # Should generate EXISTS subquery
        assert clause is not None
        sql = str(clause.compile(compile_kwargs={"literal_binds": True}))

        # Verify SQL structure
        assert "EXISTS" in sql.upper()
        assert "SELECT" in sql.upper()
        assert "ukf_id" in sql.lower()
        assert "slot" in sql.lower()
        assert "value_" in sql.lower()  # Field name is value_ not value
        assert "'TOPIC'" in sql or "TOPIC" in sql  # slot value
        assert "'math'" in sql or "math" in sql  # value_ value

    def test_nf_with_like_inside(self, adapter):
        """Test NF operator with nested LIKE operator."""
        # NF(slot="TOPIC", value_=LIKE("%math%"))
        nf_expr = KLOp.NF(slot="TOPIC", value_=KLOp.LIKE("%math%"))
        expr = KLOp.expr(tags=nf_expr)

        # Compile to SQL
        clause = SQLCompiler.compile(orms=adapter.dims, expr=expr)

        # Should generate EXISTS subquery with LIKE
        assert clause is not None
        sql = str(clause.compile(compile_kwargs={"literal_binds": True}))

        # Verify SQL structure
        assert "EXISTS" in sql.upper()
        assert "LIKE" in sql.upper()
        assert "'TOPIC'" in sql or "TOPIC" in sql
        assert "%math%" in sql

    def test_nf_with_ilike_inside(self, adapter):
        """Test NF operator with nested ILIKE operator (case-insensitive)."""
        # NF(slot="TOPIC", value_=ILIKE("%Math%"))
        nf_expr = KLOp.NF(slot="TOPIC", value_=KLOp.ILIKE("%Math%"))
        expr = KLOp.expr(tags=nf_expr)

        # Compile to SQL
        clause = SQLCompiler.compile(orms=adapter.dims, expr=expr)

        # Should generate EXISTS subquery with ILIKE/LOWER
        assert clause is not None
        sql = str(clause.compile(compile_kwargs={"literal_binds": True}))

        # Verify SQL structure
        assert "EXISTS" in sql.upper()
        # ILIKE may compile to LOWER(...) LIKE LOWER(...) or native ILIKE
        assert "ILIKE" in sql.upper() or "LOWER" in sql.upper()
        assert "'TOPIC'" in sql or "TOPIC" in sql
        assert "%Math%" in sql or "%math%" in sql

    def test_nf_with_comparison_inside(self, adapter):
        """Test NF operator with nested comparison operator."""
        # NF(slot="priority", value_=GT(5))
        nf_expr = KLOp.NF(slot="priority", value_=KLOp.GT(5))
        expr = KLOp.expr(tags=nf_expr)

        # Compile to SQL
        clause = SQLCompiler.compile(orms=adapter.dims, expr=expr)

        # Should generate EXISTS subquery with comparison
        assert clause is not None
        sql = str(clause.compile(compile_kwargs={"literal_binds": True}))

        # Verify SQL structure
        assert "EXISTS" in sql.upper()
        assert ">" in sql
        assert "'priority'" in sql or "priority" in sql
        assert "5" in sql

    def test_nf_with_like_special_chars(self, adapter):
        """Test NF operator with LIKE containing regex special characters."""
        # NF(slot="TOPIC", value_=LIKE("%c++%"))
        # This should escape + but not % (which is SQL wildcard)
        nf_expr = KLOp.NF(slot="TOPIC", value_=KLOp.LIKE("%c++%"))
        expr = KLOp.expr(tags=nf_expr)

        # Compile to SQL
        clause = SQLCompiler.compile(orms=adapter.dims, expr=expr)

        # Should not raise error and generate valid SQL
        assert clause is not None
        sql = str(clause.compile(compile_kwargs={"literal_binds": True}))

        # Verify SQL structure
        assert "EXISTS" in sql.upper()
        assert "LIKE" in sql.upper()
        assert "c++" in sql  # Literal c++

    def test_nf_combined_with_regular_field(self, adapter):
        """Test combining NF operator with regular field filters."""
        # type="tutorial" AND tags=NF(slot="TOPIC", value_=LIKE("%math%"))
        nf_expr = KLOp.NF(slot="TOPIC", value_=KLOp.LIKE("%math%"))
        expr = KLOp.expr(type="tutorial", tags=nf_expr)

        # Compile to SQL
        clause = SQLCompiler.compile(orms=adapter.dims, expr=expr)

        # Should combine both conditions with AND
        assert clause is not None
        sql = str(clause.compile(compile_kwargs={"literal_binds": True}))

        # Verify both conditions present
        assert "type" in sql.lower()
        assert "'tutorial'" in sql or "tutorial" in sql
        assert "EXISTS" in sql.upper()
        assert "LIKE" in sql.upper()
        assert "%math%" in sql
