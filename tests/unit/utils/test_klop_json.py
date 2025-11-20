"""
Tests for KLOp JSON and nested field query support.

This module tests KLOp's ability to query nested JSON fields,
particularly for MongoDB's dot notation and content_resources queries.
"""

import pytest
from typing import Any, Dict

from ahvn.utils.klop import KLOp
from ahvn.utils.mdb.compiler import MongoCompiler


class TestJSONFieldFilters:
    """Test KLOp support for JSON/nested field queries."""

    def test_simple_json_query(self):
        """Test basic JSON path query."""
        # Query nested field: content_resources.type
        expr = KLOp.expr(content_resources=KLOp.JSON(type="categorical"))

        expected = {"FIELD:content_resources": {"JSON": {"type": "categorical"}}}
        assert expr == expected

    def test_json_with_comparison_operators(self):
        """Test JSON path with comparison operators."""
        # Query: content_resources.n_records > 100
        expr = KLOp.expr(content_resources=KLOp.JSON(n_records=KLOp.GT(100)))

        expected = {"FIELD:content_resources": {"JSON": {"n_records": {">": 100}}}}
        assert expr == expected

    def test_multiple_json_queries(self):
        """Test multiple JSON path queries combined."""
        expr = KLOp.expr(content_resources=KLOp.JSON(type="categorical", n_records=KLOp.GTE(10)))

        expected = {"FIELD:content_resources": {"JSON": {"type": "categorical", "n_records": {">=": 10}}}}
        assert expr == expected

    def test_json_query_mongo_compilation(self):
        """Test that JSON queries compile correctly to MongoDB MQL."""
        expr = KLOp.expr(content_resources=KLOp.JSON(type="categorical"))

        mql = MongoCompiler.compile(expr=expr)

        # MongoDB should use dot notation
        expected = {"content_resources.type": "categorical"}
        assert mql == expected

    def test_complex_json_mongo_compilation(self):
        """Test complex JSON query compilation to MongoDB."""
        expr = KLOp.expr(content_resources=KLOp.JSON(type="categorical", n_records=KLOp.GTE(10)))

        mql = MongoCompiler.compile(expr=expr)

        expected = {
            "$and": [
                {"content_resources.type": "categorical"},
                {"content_resources.n_records": {"$gte": 10}},
            ]
        }
        assert mql == expected

    def test_json_with_string_operators(self):
        """Test JSON query with string pattern matching."""
        expr = KLOp.expr(content_resources=KLOp.JSON(description=KLOp.LIKE("%test%")))

        mql = MongoCompiler.compile(expr=expr)

        expected = {"content_resources.description": {"$regex": ".*test.*"}}
        assert mql == expected


class TestNormalizedFormFilters:
    """Test KLOp NF operator for tags/auths queries."""

    def test_nf_basic(self):
        """Test basic NF query."""
        expr = KLOp.expr(tags=KLOp.NF(slot="category", value="security"))

        expected = {"FIELD:tags": {"NF": {"slot": "category", "value": "security"}}}
        assert expr == expected

    def test_nf_with_operators(self):
        """Test NF with comparison operators."""
        expr = KLOp.expr(tags=KLOp.NF(slot="priority", value=KLOp.GTE(5)))

        expected = {"FIELD:tags": {"NF": {"slot": "priority", "value": {">=": 5}}}}
        assert expr == expected

    def test_nf_mongo_compilation(self):
        """Test NF compilation to MongoDB $elemMatch."""
        expr = KLOp.expr(tags=KLOp.NF(slot="category", value="security"))

        mql = MongoCompiler.compile(expr=expr)

        expected = {"tags": {"$elemMatch": {"slot": "category", "value": "security"}}}
        assert mql == expected

    def test_multiple_nf_queries(self):
        """Test multiple NF queries combined with AND."""
        expr = KLOp.expr(tags=KLOp.AND([KLOp.NF(slot="category", value="security"), KLOp.NF(slot="type", value="research")]))

        mql = MongoCompiler.compile(expr=expr)

        expected = {
            "$and": [{"tags": {"$elemMatch": {"slot": "category", "value": "security"}}}, {"tags": {"$elemMatch": {"slot": "type", "value": "research"}}}]
        }
        assert mql == expected


class TestFieldExistence:
    """Test field existence checks using None value."""

    def test_field_exists_with_none(self):
        """Test field existence check using None."""
        expr = KLOp.expr(description=None)

        expected = {"FIELD:description": ...}
        assert expr == expected

    def test_field_not_exists_with_not_none(self):
        """Test field non-existence check using NOT(None)."""
        expr = KLOp.expr(optional_field=KLOp.NOT(None))

        expected = {"FIELD:optional_field": {"NOT": ...}}
        assert expr == expected

    def test_exists_mongo_compilation(self):
        """Test existence check compilation to MongoDB $exists."""
        expr = KLOp.expr(description=None)

        mql = MongoCompiler.compile(expr=expr)

        expected = {"description": {"$exists": True}}
        assert mql == expected

    def test_not_exists_mongo_compilation(self):
        """Test non-existence check compilation to MongoDB."""
        expr = KLOp.expr(optional_field=KLOp.NOT(None))

        mql = MongoCompiler.compile(expr=expr)

        expected = {"optional_field": {"$exists": False}}
        assert mql == expected

    def test_json_nested_field_exists(self):
        """Test nested field existence check using JSON with Ellipsis."""
        expr = KLOp.expr(metadata=KLOp.JSON(**{"user.email": ...}))

        expected = {"FIELD:metadata": {"JSON": {"user.email": ...}}}
        assert expr == expected

    def test_json_nested_field_exists_mongo(self):
        """Test nested field existence MongoDB compilation."""
        expr = KLOp.expr(metadata=KLOp.JSON(**{"user.email": ...}))

        mql = MongoCompiler.compile(expr=expr)

        expected = {"metadata.user.email": {"$exists": True}}
        assert mql == expected

    def test_json_nested_field_not_exists_mongo(self):
        """Test nested field non-existence MongoDB compilation."""
        expr = KLOp.expr(metadata=KLOp.JSON(optional=KLOp.NOT(...)))

        mql = MongoCompiler.compile(expr=expr)

        expected = {"metadata.optional": {"$exists": False}}
        assert mql == expected
