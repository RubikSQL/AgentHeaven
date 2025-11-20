"""
Comprehensive tests for KLOp expression functionality (SQL backend).

This module tests the KLOp class's expr method across different scenarios,
including simple values, operators, and complex nested expressions.
"""

import pytest
import datetime
from typing import Any, Dict, List

from ahvn.utils.klop import KLOp


class TestFacetExpr:
    """Test KLOp expression parsing and generation."""

    def test_simple_value_expr(self):
        """Test expression generation for simple values."""
        # String value
        result = KLOp.expr(name="test")
        expected = {"FIELD:name": {"==": "test"}}
        assert result == expected

        # Numeric value
        result = KLOp.expr(count=42)
        expected = {"FIELD:count": {"==": 42}}
        assert result == expected

        # Boolean value
        result = KLOp.expr(active=True)
        expected = {"FIELD:active": {"==": True}}
        assert result == expected

    def test_like_operator_expr(self):
        """Test LIKE operator expressions."""
        result = KLOp.expr(name=KLOp.LIKE("%test%"))
        expected = {"FIELD:name": {"LIKE": "%test%"}}
        assert result == expected

        result = KLOp.expr(description=KLOp.LIKE("start%"))
        expected = {"FIELD:description": {"LIKE": "start%"}}
        assert result == expected

    def test_ilike_operator_expr(self):
        """Test ILIKE operator expressions."""
        result = KLOp.expr(name=KLOp.ILIKE("%test%"))
        expected = {"FIELD:name": {"ILIKE": "%test%"}}
        assert result == expected

    def test_comparison_operators_expr(self):
        """Test comparison operators (LT, LTE, GT, GTE)."""
        # Less than
        result = KLOp.expr(score=KLOp.LT(100))
        expected = {"FIELD:score": {"<": 100}}
        assert result == expected

        # Less than or equal
        result = KLOp.expr(score=KLOp.LTE(100))
        expected = {"FIELD:score": {"<=": 100}}
        assert result == expected

        # Greater than
        result = KLOp.expr(score=KLOp.GT(50))
        expected = {"FIELD:score": {">": 50}}
        assert result == expected

        # Greater than or equal
        result = KLOp.expr(score=KLOp.GTE(50))
        expected = {"FIELD:score": {">=": 50}}
        assert result == expected

    def test_between_operator_expr(self):
        """Test BETWEEN operator expressions."""
        result = KLOp.expr(score=KLOp.BETWEEN(0, 100))
        expected = {"FIELD:score": {"AND": [{">=": 0}, {"<=": 100}]}}
        assert result == expected

        # Test with None values (infinity)
        result = KLOp.expr(score=KLOp.BETWEEN(None, 100))
        expected = {"FIELD:score": {"AND": [{">=": float("-inf")}, {"<=": 100}]}}
        assert result == expected

    def test_datetime_operators_expr(self):
        """Test comparison operators with datetime values."""
        test_date = datetime.datetime(2024, 1, 1, 12, 0, 0)

        result = KLOp.expr(created_at=KLOp.GTE(test_date))
        expected = {"FIELD:created_at": {">=": test_date}}
        assert result == expected

        result = KLOp.expr(updated_at=KLOp.LTE(test_date))
        expected = {"FIELD:updated_at": {"<=": test_date}}
        assert result == expected

    def test_logical_operators_expr(self):
        """Test logical operators (AND, OR, NOT)."""
        # AND operator
        result = KLOp.expr(status=KLOp.AND([KLOp.LIKE("%active%"), KLOp.NOT("inactive")]))
        expected = {"FIELD:status": {"AND": [{"LIKE": "%active%"}, {"NOT": {"==": "inactive"}}]}}
        assert result == expected

        # OR operator (same as IN)
        result = KLOp.expr(status=KLOp.OR(["active", "pending", "completed"]))
        expected = {"FIELD:status": {"OR": [{"IN": ["active", "pending", "completed"]}]}}
        assert result == expected

        # NOT operator
        result = KLOp.expr(status=KLOp.NOT("deleted"))
        expected = {"FIELD:status": {"NOT": {"==": "deleted"}}}
        assert result == expected

    def test_list_expr(self):
        """Test expression generation for lists (converted to OR/IN)."""
        # Simple list
        result = KLOp.expr(status=["active", "pending"])
        expected = {"FIELD:status": {"OR": [{"IN": ["active", "pending"]}]}}
        assert result == expected

        # List with operators
        result = KLOp.expr(score=[KLOp.GTE(80), KLOp.LIKE("%A%")])
        expected = {"FIELD:score": {"OR": [{">=": 80}, {"LIKE": "%A%"}]}}
        assert result == expected

    def test_tuple_expr(self):
        """Test expression generation for tuples (converted to range)."""
        result = KLOp.expr(score=(10, 20))
        expected = {"FIELD:score": {"AND": [{">=": 10}, {"<=": 20}]}}
        assert result == expected

        # Test with None values
        result = KLOp.expr(score=(None, 100))
        expected = {"FIELD:score": {"AND": [{">=": float("-inf")}, {"<=": 100}]}}
        assert result == expected

    def test_nf_operator_expr(self):
        """Test NF (null/empty) operator expressions."""
        result = KLOp.expr(tags=KLOp.NF(slot="priority", value="high"))
        expected = {"FIELD:tags": {"NF": {"slot": "priority", "value": "high"}}}
        assert result == expected

        # Multiple NF conditions
        result = KLOp.expr(tags=KLOp.NF(slot="priority", value="high", category="urgent"))
        expected = {"FIELD:tags": {"NF": {"slot": "priority", "value": "high", "category": "urgent"}}}
        assert result == expected

    def test_multiple_field_expr(self):
        """Test expression generation with multiple fields (creates AND structure)."""
        result = KLOp.expr(name=KLOp.LIKE("%test%"), status="active", score=KLOp.GTE(80))
        expected = {"AND": [{"FIELD:name": {"LIKE": "%test%"}}, {"FIELD:status": {"==": "active"}}, {"FIELD:score": {">=": 80}}]}
        assert result == expected

    def test_single_field_expr(self):
        """Test expression generation with single field (no AND wrapper)."""
        result = KLOp.expr(name="test")
        expected = {"FIELD:name": {"==": "test"}}
        assert result == expected

    def test_empty_expr(self):
        """Test expression generation with no fields."""
        result = KLOp.expr()
        assert result is None

    def test_complex_nested_expr(self):
        """Test complex nested expressions with multiple operators."""
        result = KLOp.expr(
            name=KLOp.LIKE("%user%"),
            status=KLOp.OR(["active", "pending"]),
            score=KLOp.AND([KLOp.GTE(0), KLOp.LTE(100)]),
            created_at=KLOp.GTE(datetime.datetime(2024, 1, 1)),
            tags=KLOp.NF(slot="category", value="premium"),
            metadata=KLOp.NOT("deleted"),
        )
        expected = {
            "AND": [
                {"FIELD:name": {"LIKE": "%user%"}},
                {"FIELD:status": {"OR": [{"IN": ["active", "pending"]}]}},
                {"FIELD:score": {"AND": [{">=": 0}, {"<=": 100}]}},
                {"FIELD:created_at": {">=": datetime.datetime(2024, 1, 1)}},
                {"FIELD:tags": {"NF": {"slot": "category", "value": "premium"}}},
                {"FIELD:metadata": {"NOT": {"==": "deleted"}}},
            ]
        }
        assert result == expected

    def test_mixed_values_and_operators_in_list(self):
        """Test list with mixed simple values and operators."""
        result = KLOp.expr(priority=["high", KLOp.LIKE("%urgent%"), "critical"])
        # The order can vary, so we check structure without worrying about order
        assert "FIELD:priority" in result
        assert "OR" in result["FIELD:priority"]

        # Extract the OR items for validation
        or_items = result["FIELD:priority"]["OR"]

        # Should have both the IN operator and the LIKE operator
        found_in = any("IN" in item and set(item["IN"]) == {"high", "critical"} for item in or_items)
        found_like = any("LIKE" in item and item["LIKE"] == "%urgent%" for item in or_items)

        assert found_in
        assert found_like
        assert len(or_items) == 2

    def test_in_operator_alias(self):
        """Test IN operator (alias for OR)."""
        result = KLOp.expr(status=KLOp.IN(["active", "pending"]))
        expected = {"FIELD:status": {"OR": [{"IN": ["active", "pending"]}]}}
        assert result == expected

    def test_complex_expression_with_nested_and_or(self):
        """Test complex expression with nested AND/OR structures."""
        result = KLOp.expr(
            category=KLOp.AND([KLOp.NOT("deprecated"), KLOp.OR(["premium", "enterprise"])]),
            created_at=KLOp.BETWEEN(datetime.datetime(2023, 1, 1), datetime.datetime(2024, 12, 31)),
        )
        expected = {
            "AND": [
                {"FIELD:category": {"AND": [{"NOT": {"==": "deprecated"}}, {"OR": [{"IN": ["premium", "enterprise"]}]}]}},
                {"FIELD:created_at": {"AND": [{">=": datetime.datetime(2023, 1, 1)}, {"<=": datetime.datetime(2024, 12, 31)}]}},
            ]
        }
        assert result == expected
