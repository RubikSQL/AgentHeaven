"""Unit tests for KLOp JSON IR generation (Stage 1).

This module tests the backend-agnostic JSON intermediate representation (IR)
generation for all filter types. Stage 2 (compilation to backend-specific
formats) is tested separately in backend adapter tests.

Test Coverage:
- Basic exact match filters
- Comparison operators (GT, LT, GTE, LTE)
- Range operators (BETWEEN, tuple shorthand)
- Pattern matching (LIKE, ILIKE)
- Logical operators (AND, OR, NOT, IN)
- Normalized form (NF) for tags/auths
- MongoDB-specific operators (JSON, ELEM, SIZE, EXISTS)
- Complex nested expressions
- Edge cases (empty filters, single field, etc.)
"""

import pytest
import datetime
from ahvn.utils.klop import KLOp


class TestKLFilterBasicOperators:
    """Test basic filter operators JSON IR generation."""

    def test_exact_match_single_field(self):
        """Test exact match with a single field."""
        expr = KLOp.expr(status="active")
        assert expr == {"FIELD:status": {"==": "active"}}

    def test_exact_match_multiple_fields(self):
        """Test exact match with multiple fields (implicit AND)."""
        expr = KLOp.expr(status="active", version="v1.0.0")
        assert expr == {
            "AND": [
                {"FIELD:status": {"==": "active"}},
                {"FIELD:version": {"==": "v1.0.0"}},
            ]
        }

    def test_exact_match_various_types(self):
        """Test exact match with various value types."""
        expr = KLOp.expr(
            count=42,
            ratio=3.14,
            enabled=True,
            name="test",
        )
        assert expr == {
            "AND": [
                {"FIELD:count": {"==": 42}},
                {"FIELD:ratio": {"==": 3.14}},
                {"FIELD:enabled": {"==": True}},
                {"FIELD:name": {"==": "test"}},
            ]
        }

    def test_empty_expr(self):
        """Test empty expression."""
        expr = KLOp.expr()
        assert expr is None


class TestKLFilterComparisonOperators:
    """Test comparison operators JSON IR generation."""

    def test_greater_than(self):
        """Test GT (greater than) operator."""
        expr = KLOp.expr(priority=KLOp.GT(50))
        assert expr == {"FIELD:priority": {">": 50}}

    def test_greater_than_or_equal(self):
        """Test GTE (greater than or equal) operator."""
        expr = KLOp.expr(priority=KLOp.GTE(50))
        assert expr == {"FIELD:priority": {">=": 50}}

    def test_less_than(self):
        """Test LT (less than) operator."""
        expr = KLOp.expr(priority=KLOp.LT(100))
        assert expr == {"FIELD:priority": {"<": 100}}

    def test_less_than_or_equal(self):
        """Test LTE (less than or equal) operator."""
        expr = KLOp.expr(priority=KLOp.LTE(100))
        assert expr == {"FIELD:priority": {"<=": 100}}

    def test_multiple_comparison_operators(self):
        """Test multiple comparison operators (implicit AND)."""
        expr = KLOp.expr(
            min_val=KLOp.GT(10),
            max_val=KLOp.LT(90),
        )
        assert expr == {
            "AND": [
                {"FIELD:min_val": {">": 10}},
                {"FIELD:max_val": {"<": 90}},
            ]
        }


class TestKLFilterRangeOperators:
    """Test range operators JSON IR generation."""

    def test_between_with_both_bounds(self):
        """Test BETWEEN operator with both min and max."""
        expr = KLOp.expr(priority=KLOp.BETWEEN(0, 100))
        assert expr == {"FIELD:priority": {"AND": [{">=": 0}, {"<=": 100}]}}

    def test_between_with_min_only(self):
        """Test BETWEEN operator with min only."""
        expr = KLOp.expr(priority=KLOp.BETWEEN(min=50))
        assert expr == {"FIELD:priority": {"AND": [{">=": 50}, {"<=": float("inf")}]}}

    def test_between_with_max_only(self):
        """Test BETWEEN operator with max only."""
        expr = KLOp.expr(priority=KLOp.BETWEEN(max=100))
        assert expr == {"FIELD:priority": {"AND": [{">=": float("-inf")}, {"<=": 100}]}}

    def test_between_with_datetime(self):
        """Test BETWEEN operator with datetime values."""
        start = datetime.datetime(2024, 1, 1)
        end = datetime.datetime(2024, 12, 31)
        expr = KLOp.expr(created_at=KLOp.BETWEEN(start, end))
        assert expr == {"FIELD:created_at": {"AND": [{">=": start}, {"<=": end}]}}

    def test_tuple_shorthand_for_between(self):
        """Test tuple shorthand for BETWEEN operator."""
        expr = KLOp.expr(priority=(10, 90))
        assert expr == {"FIELD:priority": {"AND": [{">=": 10}, {"<=": 90}]}}


class TestKLFilterPatternMatching:
    """Test pattern matching operators JSON IR generation."""

    def test_like_operator(self):
        """Test LIKE operator for pattern matching."""
        expr = KLOp.expr(description=KLOp.LIKE("%security%"))
        assert expr == {"FIELD:description": {"LIKE": "%security%"}}

    def test_ilike_operator(self):
        """Test ILIKE operator for case-insensitive pattern matching."""
        expr = KLOp.expr(description=KLOp.ILIKE("%Security%"))
        assert expr == {"FIELD:description": {"ILIKE": "%Security%"}}

    def test_multiple_pattern_matches(self):
        """Test multiple pattern matching conditions."""
        expr = KLOp.expr(
            name=KLOp.LIKE("test%"),
            description=KLOp.ILIKE("%important%"),
        )
        assert expr == {
            "AND": [
                {"FIELD:name": {"LIKE": "test%"}},
                {"FIELD:description": {"ILIKE": "%important%"}},
            ]
        }


class TestKLFilterLogicalOperators:
    """Test logical operators JSON IR generation."""

    def test_not_operator(self):
        """Test NOT operator."""
        expr = KLOp.expr(description=KLOp.NOT("test"))
        assert expr == {"FIELD:description": {"NOT": {"==": "test"}}}

    def test_not_with_complex_expression(self):
        """Test NOT operator with complex expression."""
        expr = KLOp.expr(priority=KLOp.NOT(KLOp.BETWEEN(0, 100)))
        assert expr == {"FIELD:priority": {"NOT": {"AND": [{">=": 0}, {"<=": 100}]}}}

    def test_in_operator_with_values(self):
        """Test IN operator with list of values."""
        expr = KLOp.expr(status=KLOp.IN(["active", "pending", "done"]))
        assert expr == {"FIELD:status": {"OR": [{"IN": ["active", "pending", "done"]}]}}

    def test_in_operator_with_list_shorthand(self):
        """Test list shorthand for IN operator."""
        expr = KLOp.expr(status=["active", "pending"])
        assert expr == {"FIELD:status": {"OR": [{"IN": ["active", "pending"]}]}}

    def test_or_operator_with_mixed_values(self):
        """Test OR operator with mixed simple and complex values."""
        expr = KLOp.expr(priority=KLOp.OR([10, 20, KLOp.BETWEEN(50, 100)]))
        assert expr == {"FIELD:priority": {"OR": [{"AND": [{">=": 50}, {"<=": 100}]}, {"IN": [10, 20]}]}}

    def test_and_operator_explicit(self):
        """Test explicit AND operator."""
        expr = KLOp.expr(value=KLOp.AND([KLOp.GT(10), KLOp.LT(100)]))
        assert expr == {"FIELD:value": {"AND": [{">": 10}, {"<": 100}]}}


class TestKLFilterNormalizedForm:
    """Test normalized form (NF) operator for tags/auths."""

    def test_nf_simple_query(self):
        """Test NF operator with simple query."""
        expr = KLOp.expr(tags=KLOp.NF(tag={"type": "category", "value": "security"}))
        assert expr == {"FIELD:tags": {"NF": {"tag": {"type": "category", "value": "security"}}}}

    def test_nf_auth_query(self):
        """Test NF operator for auths field."""
        expr = KLOp.expr(auths=KLOp.NF(auth={"user": "alice", "permission": "read"}))
        assert expr == {"FIELD:auths": {"NF": {"auth": {"user": "alice", "permission": "read"}}}}

    def test_nf_complex_query(self):
        """Test NF operator with complex conditions."""
        expr = KLOp.expr(tags=KLOp.NF(tag={"type": "security", "level": "high", "verified": True}))
        assert expr == {"FIELD:tags": {"NF": {"tag": {"type": "security", "level": "high", "verified": True}}}}


class TestKLFilterMongoDBSpecific:
    """Test MongoDB-specific operators JSON IR generation."""

    def test_json_path_operator(self):
        """Test JSON operator for nested field queries."""
        expr = KLOp.expr(metadata=KLOp.JSON(**{"user.role": "admin"}))
        assert expr == {"FIELD:metadata": {"JSON": {"user.role": "admin"}}}

    def test_json_path_deep_nesting(self):
        """Test JSON operator with deeply nested path."""
        expr = KLOp.expr(data=KLOp.JSON(**{"level1.level2.level3.field": 42}))
        assert expr == {"FIELD:data": {"JSON": {"level1.level2.level3.field": 42}}}

    def test_field_existence_with_none(self):
        """Test field existence check using None."""
        expr = KLOp.expr(description=None)
        assert expr == {"FIELD:description": ...}

    def test_field_non_existence_with_not_none(self):
        """Test field non-existence check using NOT(None)."""
        expr = KLOp.expr(optional_field=KLOp.NOT(None))
        assert expr == {"FIELD:optional_field": {"NOT": ...}}


class TestKLFilterComplexExpressions:
    """Test complex nested filter expressions."""

    def test_mixed_operators_basic(self):
        """Test basic combination of different operators."""
        expr = KLOp.expr(
            status="active",
            priority=KLOp.BETWEEN(0, 100),
            description=KLOp.LIKE("%test%"),
        )
        assert expr == {
            "AND": [
                {"FIELD:status": {"==": "active"}},
                {"FIELD:priority": {"AND": [{">=": 0}, {"<=": 100}]}},
                {"FIELD:description": {"LIKE": "%test%"}},
            ]
        }

    def test_mixed_operators_with_not(self):
        """Test combination with NOT operator."""
        expr = KLOp.expr(
            description=KLOp.NOT("def"),
            version="v1.0.0",
            priority=KLOp.BETWEEN(0, 100),
        )
        assert expr == {
            "AND": [
                {"FIELD:description": {"NOT": {"==": "def"}}},
                {"FIELD:version": {"==": "v1.0.0"}},
                {"FIELD:priority": {"AND": [{">=": 0}, {"<=": 100}]}},
            ]
        }

    def test_all_standard_operators_combined(self):
        """Test combination of all standard operators."""
        expr = KLOp.expr(
            exact="value",
            gt_val=KLOp.GT(10),
            between_val=KLOp.BETWEEN(20, 80),
            pattern=KLOp.LIKE("%test%"),
            not_val=KLOp.NOT("excluded"),
            in_val=KLOp.IN(["a", "b", "c"]),
        )
        assert "AND" in expr
        assert len(expr["AND"]) == 6
        assert {"FIELD:exact": {"==": "value"}} in expr["AND"]
        assert {"FIELD:gt_val": {">": 10}} in expr["AND"]

    def test_mongodb_features_combined(self):
        """Test combination of MongoDB-specific features."""
        expr = KLOp.expr(
            priority=KLOp.BETWEEN(0, 100),
            status=KLOp.IN(["active", "pending"]),
            metadata=KLOp.JSON(**{"user.department": "Engineering"}),
            tags=KLOp.NF(tag={"type": "security", "level": "high"}),
        )
        assert "AND" in expr
        assert len(expr["AND"]) == 4
        # Check that all fields are present
        field_names = [list(item.keys())[0] for item in expr["AND"]]
        assert "FIELD:priority" in field_names
        assert "FIELD:status" in field_names
        assert "FIELD:metadata" in field_names
        assert "FIELD:tags" in field_names


class TestKLFilterEdgeCases:
    """Test edge cases and special scenarios."""

    def test_none_values_in_between(self):
        """Test BETWEEN with None values."""
        expr = KLOp.expr(value=KLOp.BETWEEN(None, None))
        assert expr == {"FIELD:value": {"AND": [{">=": float("-inf")}, {"<=": float("inf")}]}}

    def test_empty_list_in_or(self):
        """Test OR operator with empty list."""
        expr = KLOp.expr(status=KLOp.OR([]))
        assert expr == {"FIELD:status": {"OR": []}}

    def test_nested_not_operators(self):
        """Test nested NOT operators."""
        expr = KLOp.expr(value=KLOp.NOT(KLOp.NOT(KLOp.GT(50))))
        assert expr == {"FIELD:value": {"NOT": {"NOT": {">": 50}}}}

    def test_or_with_only_values(self):
        """Test OR operator with only simple values (no operators)."""
        expr = KLOp.expr(status=KLOp.OR(["a", "b", "c"]))
        assert expr == {"FIELD:status": {"OR": [{"IN": ["a", "b", "c"]}]}}

    def test_or_with_only_operators(self):
        """Test OR operator with only complex operators (no simple values)."""
        expr = KLOp.expr(value=KLOp.OR([KLOp.GT(10), KLOp.LT(5)]))
        assert expr == {"FIELD:value": {"OR": [{">": 10}, {"<": 5}]}}


class TestKLFilterRealWorldScenarios:
    """Test real-world filter scenarios."""

    def test_facet_search_scenario(self):
        """Test typical faceted search scenario."""
        # Search for: active items, created in 2024, priority 50-100, with tag "important"
        expr = KLOp.expr(
            status="active",
            created_year=2024,
            priority=KLOp.BETWEEN(50, 100),
            tags=KLOp.NF(tag={"type": "importance", "value": "high"}),
        )
        assert "AND" in expr
        assert len(expr["AND"]) == 4

    def test_vector_search_with_metadata_filters(self):
        """Test vector search scenario with metadata filtering."""
        # Vector search with filters: status active, recent, has description
        expr = KLOp.expr(
            status=KLOp.IN(["active", "pending"]),
            created_at=KLOp.GT(datetime.datetime(2024, 1, 1)),
            description=None,  # Field exists
        )
        assert "AND" in expr
        assert len(expr["AND"]) == 3

    def test_mongodb_json_query_scenario(self):
        """Test MongoDB nested JSON query scenario."""
        # Query nested user data in metadata
        expr = KLOp.expr(
            metadata=KLOp.JSON(**{"user.role": "admin"}),
            metadata2=KLOp.JSON(**{"user.department": "Engineering"}),
            status="active",
        )
        # Note: This creates two separate metadata fields in expr
        # In real usage, you'd handle nested paths differently
        assert "AND" in expr
        assert len(expr["AND"]) == 3

    def test_complex_authorization_query(self):
        """Test complex authorization query with auths."""
        # Query: user has read OR write permission, and resource is verified
        expr = KLOp.expr(
            auths=KLOp.NF(auth={"user": "alice", "permissions": ["read", "write"]}),
            verified=True,
        )
        assert "AND" in expr
        assert len(expr["AND"]) == 2

    def test_search_with_exclusions(self):
        """Test search with explicit exclusions."""
        # Search: active status, NOT archived, priority > 0, NOT in [1, 2, 3]
        expr = KLOp.expr(
            status="active",
            archived=KLOp.NOT(True),
            priority=KLOp.GT(0),
            id=KLOp.NOT(KLOp.IN([1, 2, 3])),
        )
        assert "AND" in expr
        assert len(expr["AND"]) == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
