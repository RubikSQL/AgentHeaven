"""
Tests for MongoDB compiler backend with KLOp operators.

This module tests compilation of KLOp JSON IR to MongoDB MQL.
Focuses on operators with special compilation requirements:
- LIKE/ILIKE: Pattern matching with proper regex escaping
- JSON: Nested field queries with dot notation
- NF: Normalized form queries with $elemMatch
"""

import pytest
from ahvn.utils.klop import KLOp
from ahvn.utils.mdb.compiler import MongoCompiler


class TestLIKEOperatorMongoDB:
    """Test LIKE and ILIKE operator compilation for MongoDB with regex escaping."""

    def test_like_basic(self):
        """Test basic LIKE operator compiles to MongoDB $regex."""
        expr = KLOp.expr(name=KLOp.LIKE("%test%"))
        mql = MongoCompiler.compile(expr=expr)

        assert "name" in mql
        assert "$regex" in mql["name"]
        assert mql["name"]["$regex"] == ".*test.*"

    def test_ilike_case_insensitive(self):
        """Test ILIKE compiles to case-insensitive MongoDB regex."""
        expr = KLOp.expr(title=KLOp.ILIKE("%python%"))
        mql = MongoCompiler.compile(expr=expr)

        assert "$regex" in mql["title"]
        assert "$options" in mql["title"]
        assert mql["title"]["$options"] == "i"

    def test_like_escapes_parentheses(self):
        """Test LIKE escapes regex special characters: ()"""
        expr = KLOp.expr(code=KLOp.LIKE("%function(x)%"))
        mql = MongoCompiler.compile(expr=expr)

        pattern = mql["code"]["$regex"]
        # Parentheses should be escaped: \( and \)
        assert pattern == r".*function\(x\).*"

    def test_like_escapes_square_brackets(self):
        """Test LIKE escapes square brackets []"""
        expr = KLOp.expr(code=KLOp.LIKE("%array[0]%"))
        mql = MongoCompiler.compile(expr=expr)

        pattern = mql["code"]["$regex"]
        # Square brackets should be escaped
        assert pattern == r".*array\[0\].*"

    def test_like_escapes_special_chars(self):
        """Test LIKE escapes multiple regex special characters."""
        expr = KLOp.expr(pattern=KLOp.LIKE("%a+b*c.d?e^f$g|h%"))
        mql = MongoCompiler.compile(expr=expr)

        pattern = mql["pattern"]["$regex"]
        # All regex special chars should be escaped
        assert pattern == r".*a\+b\*c\.d\?e\^f\$g\|h.*"

    def test_like_escapes_backslash(self):
        """Test LIKE escapes backslash character."""
        expr = KLOp.expr(path=KLOp.LIKE("%dir\\file%"))
        mql = MongoCompiler.compile(expr=expr)

        pattern = mql["path"]["$regex"]
        # Backslash should be escaped
        assert pattern == r".*dir\\file.*"

    def test_like_wildcard_positions(self):
        """Test LIKE wildcards at various positions."""
        # Leading wildcard
        expr1 = KLOp.expr(name=KLOp.LIKE("%end"))
        mql1 = MongoCompiler.compile(expr=expr1)
        assert mql1["name"]["$regex"] == ".*end"

        # Trailing wildcard
        expr2 = KLOp.expr(name=KLOp.LIKE("start%"))
        mql2 = MongoCompiler.compile(expr=expr2)
        assert mql2["name"]["$regex"] == "start.*"

        # Middle wildcard with special chars
        expr3 = KLOp.expr(code=KLOp.LIKE("func(%)end"))
        mql3 = MongoCompiler.compile(expr=expr3)
        assert mql3["code"]["$regex"] == r"func\(.*\)end"

    def test_like_underscore_wildcard(self):
        """Test LIKE underscore _ wildcard (single character)."""
        expr = KLOp.expr(code=KLOp.LIKE("a_b"))
        mql = MongoCompiler.compile(expr=expr)

        # Underscore should convert to . (single char wildcard in regex)
        assert mql["code"]["$regex"] == "a.b"

    def test_like_mixed_wildcards(self):
        """Test LIKE with mixed % and _ wildcards."""
        expr = KLOp.expr(pattern=KLOp.LIKE("%a_b%"))
        mql = MongoCompiler.compile(expr=expr)

        # % → .*, _ → .
        assert mql["pattern"]["$regex"] == ".*a.b.*"

    def test_like_complex_pattern(self):
        """Test LIKE with complex pattern including wildcards and special chars."""
        # Pattern: %fibonacci(n=%)
        expr = KLOp.expr(name=KLOp.LIKE("%fibonacci(n=%"))
        mql = MongoCompiler.compile(expr=expr)

        pattern = mql["name"]["$regex"]
        # Should escape ( and ) but convert % to .*
        assert pattern == r".*fibonacci\(n=.*"

    def test_ilike_escapes_with_case_insensitive(self):
        """Test ILIKE escapes special characters while maintaining case-insensitivity."""
        expr = KLOp.expr(title=KLOp.ILIKE("%function(%)%"))
        mql = MongoCompiler.compile(expr=expr)

        assert mql["title"]["$regex"] == r".*function\(.*\).*"
        assert mql["title"]["$options"] == "i"


class TestJSONOperatorMongoDB:
    """Test JSON operator compilation for MongoDB."""

    def test_json_basic(self):
        """Test basic JSON field access."""
        expr = KLOp.expr(metadata=KLOp.JSON(status="active"))
        mql = MongoCompiler.compile(expr=expr)

        # Should use dot notation
        assert "metadata.status" in mql
        assert mql["metadata.status"] == "active"

    def test_json_nested_path(self):
        """Test JSON with nested path using dot notation in key."""
        expr = KLOp.expr(data=KLOp.JSON(**{"user.role.permissions": "admin"}))
        mql = MongoCompiler.compile(expr=expr)

        assert "data.user.role.permissions" in mql
        assert mql["data.user.role.permissions"] == "admin"

    def test_json_with_comparison(self):
        """Test JSON with comparison operators."""
        expr = KLOp.expr(stats=KLOp.JSON(views=KLOp.GT(1000)))
        mql = MongoCompiler.compile(expr=expr)

        assert "stats.views" in mql
        assert "$gt" in mql["stats.views"]
        assert mql["stats.views"]["$gt"] == 1000

    def test_json_existence_check(self):
        """Test JSON field existence using Ellipsis."""
        expr = KLOp.expr(metadata=KLOp.JSON(created_at=...))
        mql = MongoCompiler.compile(expr=expr)

        # Should compile to existence check
        assert "metadata.created_at" in mql
        assert "$exists" in mql["metadata.created_at"]
        assert mql["metadata.created_at"]["$exists"] is True

    def test_json_in_operator(self):
        """Test JSON with IN operator."""
        expr = KLOp.expr(config=KLOp.JSON(environment=KLOp.IN(["dev", "staging", "prod"])))
        mql = MongoCompiler.compile(expr=expr)

        # IN with JSON compiles to nested structure
        assert "config.environment" in mql

    def test_json_kwargs_basic(self):
        """Test JSON with multiple kwargs (AND of all conditions)."""
        expr = KLOp.expr(metadata=KLOp.JSON(type="categorical", status="active"))
        mql = MongoCompiler.compile(expr=expr)

        # Should compile to $and with both conditions
        assert "$and" in mql
        conditions = mql["$and"]

        # Check both conditions are present
        paths = set()
        for cond in conditions:
            paths.update(cond.keys())

        assert "metadata.type" in paths
        assert "metadata.status" in paths

        # Verify values
        type_cond = next(c for c in conditions if "metadata.type" in c)
        status_cond = next(c for c in conditions if "metadata.status" in c)
        assert type_cond["metadata.type"] == "categorical"
        assert status_cond["metadata.status"] == "active"

    def test_json_kwargs_with_operators(self):
        """Test JSON kwargs with comparison operators."""
        expr = KLOp.expr(metadata=KLOp.JSON(count=KLOp.GT(100), status=KLOp.IN(["active", "pending"])))
        mql = MongoCompiler.compile(expr=expr)

        # Should compile to $and with both conditions
        assert "$and" in mql
        conditions = mql["$and"]

        # Find conditions
        count_cond = next((c for c in conditions if "metadata.count" in c), None)
        status_cond = next((c for c in conditions if "metadata.status" in c), None)

        assert count_cond is not None
        assert status_cond is not None

        # Verify operators
        assert "$gt" in count_cond["metadata.count"]
        assert count_cond["metadata.count"]["$gt"] == 100
        assert "$in" in status_cond["metadata.status"]
        assert set(status_cond["metadata.status"]["$in"]) == {"active", "pending"}

    def test_json_kwargs_single_field(self):
        """Test JSON kwargs with a single field (should not wrap in $and)."""
        expr = KLOp.expr(metadata=KLOp.JSON(status="active"))
        mql = MongoCompiler.compile(expr=expr)

        # Single condition should not be wrapped in $and
        assert "metadata.status" in mql
        assert mql["metadata.status"] == "active"


class TestNFOperatorMongoDB:
    """Test NF (Normalized Form) operator compilation for MongoDB."""

    def test_nf_basic(self):
        """Test basic NF operator compiles to MongoDB $elemMatch."""
        expr = KLOp.expr(tags=KLOp.NF(slot="TOPIC", value="security"))
        mql = MongoCompiler.compile(expr=expr)

        assert "tags" in mql
        assert "$elemMatch" in mql["tags"]
        elem_match = mql["tags"]["$elemMatch"]
        assert elem_match["slot"] == "TOPIC"
        assert elem_match["value"] == "security"

    def test_nf_with_multiple_fields(self):
        """Test NF with multiple field conditions."""
        expr = KLOp.expr(auths=KLOp.NF(slot="USER", value="alice", priority=5))
        mql = MongoCompiler.compile(expr=expr)

        elem_match = mql["auths"]["$elemMatch"]
        assert elem_match["slot"] == "USER"
        assert elem_match["value"] == "alice"
        assert elem_match["priority"] == 5

    def test_nf_with_comparison_operators(self):
        """Test NF with comparison operators on values."""
        expr = KLOp.expr(metrics=KLOp.NF(slot="SCORE", value=KLOp.GTE(90)))
        mql = MongoCompiler.compile(expr=expr)

        elem_match = mql["metrics"]["$elemMatch"]
        assert elem_match["slot"] == "SCORE"
        assert "$gte" in elem_match["value"]
        assert elem_match["value"]["$gte"] == 90

    def test_nf_with_like_inside(self):
        """Test NF with LIKE operator on value field."""
        expr = KLOp.expr(tags=KLOp.NF(slot="TOPIC", value=KLOp.LIKE("%math%")))
        mql = MongoCompiler.compile(expr=expr)

        # Should use $elemMatch with $regex inside
        assert "tags" in mql
        assert "$elemMatch" in mql["tags"]
        elem_match = mql["tags"]["$elemMatch"]
        assert elem_match["slot"] == "TOPIC"
        assert "$regex" in elem_match["value"]
        assert elem_match["value"]["$regex"] == ".*math.*"

    def test_nf_with_ilike_inside(self):
        """Test NF with ILIKE operator on value field."""
        expr = KLOp.expr(tags=KLOp.NF(slot="TOPIC", value=KLOp.ILIKE("%Math%")))
        mql = MongoCompiler.compile(expr=expr)

        # Should use $elemMatch with case-insensitive $regex inside
        elem_match = mql["tags"]["$elemMatch"]
        assert elem_match["slot"] == "TOPIC"
        assert "$regex" in elem_match["value"]
        assert "$options" in elem_match["value"]
        assert elem_match["value"]["$options"] == "i"
        assert elem_match["value"]["$regex"] == ".*Math.*"

    def test_nf_with_like_special_chars(self):
        """Test NF with LIKE containing regex special characters."""
        expr = KLOp.expr(tags=KLOp.NF(slot="NOTE", value=KLOp.LIKE("%fibonacci(n=%)%")))
        mql = MongoCompiler.compile(expr=expr)

        # Special chars should be escaped
        elem_match = mql["tags"]["$elemMatch"]
        assert elem_match["slot"] == "NOTE"
        pattern = elem_match["value"]["$regex"]
        # Parentheses should be escaped
        assert r"\(" in pattern
        assert r"\)" in pattern


class TestCombinedOperatorsMongoDB:
    """Test combined operators for MongoDB."""

    def test_like_and_json(self):
        """Test combination of LIKE and JSON operators."""
        expr = KLOp.expr(name=KLOp.LIKE("%test%"), metadata=KLOp.JSON(status="active"))
        mql = MongoCompiler.compile(expr=expr)

        # Should have both conditions
        assert "name" in mql or "$and" in mql
        assert "metadata.status" in str(mql)

    def test_nf_with_like(self):
        """Test NF combined with LIKE operator."""
        expr = KLOp.expr(tags=KLOp.NF(slot="TOPIC", value=KLOp.LIKE("%security%")), name=KLOp.LIKE("%system%"))
        mql = MongoCompiler.compile(expr=expr)

        # Both operators should be present
        assert "tags" in str(mql) or "$and" in str(mql)
        assert "name" in str(mql) or "$and" in str(mql)


class TestEdgeCasesMongoDB:
    """Test edge cases for MongoDB compilation."""

    def test_empty_pattern(self):
        """Test LIKE with empty pattern."""
        expr = KLOp.expr(name=KLOp.LIKE(""))
        mql = MongoCompiler.compile(expr=expr)

        # Empty pattern should still compile
        assert "name" in mql

    def test_only_wildcards(self):
        """Test LIKE with only wildcards."""
        expr = KLOp.expr(name=KLOp.LIKE("%%%"))
        mql = MongoCompiler.compile(expr=expr)

        pattern = mql["name"]["$regex"]
        # Should collapse to .*
        assert ".*" in pattern

    def test_json_empty_path(self):
        """Test JSON with minimal path."""
        expr = KLOp.expr(data=KLOp.JSON(key="value"))
        mql = MongoCompiler.compile(expr=expr)

        assert "data.key" in mql

    def test_empty_or(self):
        """Test OR([]) compiles to never-match condition."""
        expr = KLOp.OR([])
        mql = MongoCompiler.compile(expr=KLOp._expr(expr))

        # Should be a condition that never matches - using $literal False
        assert "$literal" in mql
        assert mql["$literal"] is False

    def test_empty_and(self):
        """Test AND([]) compiles to match-all condition."""
        expr = KLOp.AND([])
        mql = MongoCompiler.compile(expr=KLOp._expr(expr))

        # Should be empty dict (match all)
        assert mql == {}

    def test_empty_in(self):
        """Test IN([]) compiles to never-match condition."""
        expr = KLOp.expr(status=KLOp.IN([]))
        mql = MongoCompiler.compile(expr=expr)

        # Should be a condition that never matches - using $literal False
        assert "$literal" in mql
        assert mql["$literal"] is False

    def test_or_with_empty_in(self):
        """Test OR containing an empty IN still evaluates correctly."""
        # OR([status IN [], priority > 5]) should match only priority > 5
        combined = {"OR": [{"FIELD:status": {"OR": []}}, {"FIELD:priority": {">": 5}}]}
        mql = MongoCompiler.compile(expr=combined)

        # Should have $or with never-match and priority condition
        assert "$or" in mql
        assert len(mql["$or"]) == 2
        # First condition is never-match using $literal False
        assert "$literal" in mql["$or"][0]
        assert mql["$or"][0]["$literal"] is False
        # Second condition is the priority filter
        assert "priority" in mql["$or"][1]

    def test_and_with_empty_in(self):
        """Test AND containing an empty IN never matches."""
        # AND([status IN [], priority > 5]) should never match
        combined = {"AND": [{"FIELD:status": {"OR": []}}, {"FIELD:priority": {">": 5}}]}
        mql = MongoCompiler.compile(expr=combined)

        # Should have $and with both conditions
        assert "$and" in mql
        # First condition is never-match using $literal False, making the entire AND never match
        assert "$literal" in mql["$and"][0]
        assert mql["$and"][0]["$literal"] is False
        assert "priority" in mql["$and"][1]
