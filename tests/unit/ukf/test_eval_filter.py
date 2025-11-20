"""Tests for BaseUKF.eval_filter method."""

import pytest
from ahvn.ukf.base import BaseUKF
from ahvn.utils.klop import KLOp


class TestEvalFilterBasic:
    """Test basic eval_filter functionality."""

    def test_simple_equality(self):
        """Test simple field equality."""
        ukf = BaseUKF(name="test", priority=50, type="document")
        assert ukf.eval_filter(priority=50)
        assert not ukf.eval_filter(priority=100)
        assert ukf.eval_filter(type="document")

    def test_no_filter_returns_true(self):
        """Test that no filter means match all."""
        ukf = BaseUKF(name="test", type="document")
        assert ukf.eval_filter()

    def test_nonexistent_field(self):
        """Test filtering on nonexistent field returns False."""
        ukf = BaseUKF(name="test", type="document")
        assert not ukf.eval_filter(nonexistent_field="value")


class TestEvalFilterComparison:
    """Test comparison operators."""

    def test_gt_operator(self):
        """Test greater than operator."""
        ukf = BaseUKF(name="test", priority=50, type="document")
        assert ukf.eval_filter(priority=KLOp.GT(40))
        assert not ukf.eval_filter(priority=KLOp.GT(60))

    def test_gte_operator(self):
        """Test greater than or equal operator."""
        ukf = BaseUKF(name="test", priority=50, type="document")
        assert ukf.eval_filter(priority=KLOp.GTE(50))
        assert ukf.eval_filter(priority=KLOp.GTE(40))
        assert not ukf.eval_filter(priority=KLOp.GTE(60))

    def test_lt_operator(self):
        """Test less than operator."""
        ukf = BaseUKF(name="test", priority=50, type="document")
        assert ukf.eval_filter(priority=KLOp.LT(60))
        assert not ukf.eval_filter(priority=KLOp.LT(40))

    def test_lte_operator(self):
        """Test less than or equal operator."""
        ukf = BaseUKF(name="test", priority=50, type="document")
        assert ukf.eval_filter(priority=KLOp.LTE(50))
        assert ukf.eval_filter(priority=KLOp.LTE(60))
        assert not ukf.eval_filter(priority=KLOp.LTE(40))


class TestEvalFilterRange:
    """Test range operators."""

    def test_between_operator(self):
        """Test BETWEEN operator."""
        ukf = BaseUKF(name="test", priority=50, type="document")
        assert ukf.eval_filter(priority=KLOp.BETWEEN(0, 100))
        assert ukf.eval_filter(priority=KLOp.BETWEEN(50, 50))
        assert not ukf.eval_filter(priority=KLOp.BETWEEN(60, 100))
        assert not ukf.eval_filter(priority=KLOp.BETWEEN(0, 40))


class TestEvalFilterMultiple:
    """Test multiple conditions."""

    def test_multiple_kwargs_and(self):
        """Test multiple kwargs are ANDed together."""
        ukf = BaseUKF(name="test", priority=50, type="document")
        assert ukf.eval_filter(priority=50, type="document")
        assert not ukf.eval_filter(priority=50, type="other")
        assert not ukf.eval_filter(priority=100, type="document")

    def test_combined_operators(self):
        """Test combining different operators."""
        ukf = BaseUKF(name="test", priority=50, type="document")
        assert ukf.eval_filter(priority=KLOp.BETWEEN(0, 100), type="document")
        assert not ukf.eval_filter(priority=KLOp.GT(60), type="document")


class TestEvalFilterPattern:
    """Test pattern matching."""

    def test_like_operator(self):
        """Test LIKE pattern matching."""
        ukf = BaseUKF(name="test", description="This is a test", type="document")
        assert ukf.eval_filter(description=KLOp.LIKE(".*test.*"))
        assert ukf.eval_filter(description=KLOp.LIKE("This.*"))
        assert not ukf.eval_filter(description=KLOp.LIKE(".*nonexistent.*"))

    def test_ilike_operator(self):
        """Test ILIKE case-insensitive pattern matching."""
        ukf = BaseUKF(name="test", description="This is a TEST", type="document")
        assert ukf.eval_filter(description=KLOp.ILIKE(".*test.*"))
        assert ukf.eval_filter(description=KLOp.ILIKE(".*TEST.*"))
        assert ukf.eval_filter(description=KLOp.ILIKE("this.*"))


class TestEvalFilterIn:
    """Test IN operator."""

    def test_in_operator(self):
        """Test IN operator for membership testing."""
        ukf = BaseUKF(name="test", type="document")
        assert ukf.eval_filter(type=KLOp.IN(["document", "file"]))
        assert not ukf.eval_filter(type=KLOp.IN(["other", "unknown"]))


class TestEvalFilterParsed:
    """Test using parsed KLOp expressions."""

    def test_parsed_expression(self):
        """Test using a pre-parsed KLOp expression."""
        ukf = BaseUKF(name="test", priority=50, type="document")
        expr = KLOp.expr(priority=KLOp.GT(40), type="document")
        assert ukf.eval_filter(expr)

        expr2 = KLOp.expr(priority=KLOp.GT(60))
        assert not ukf.eval_filter(expr2)

    def test_combined_filter_and_kwargs(self):
        """Test combining parsed filter with additional kwargs."""
        ukf = BaseUKF(name="test", priority=50, type="document", version="v1.0")
        expr = KLOp.expr(priority=KLOp.GT(40))
        assert ukf.eval_filter(expr, type="document")
        assert ukf.eval_filter(expr, type="document", version="v1.0")
        assert not ukf.eval_filter(expr, type="other")


class TestEvalFilterJSON:
    """Test JSON operator for nested field access."""

    def test_json_simple(self):
        """Test JSON operator with simple nested path."""
        ukf = BaseUKF(
            name="test",
            type="document",
            metadata={"user": {"role": "admin", "level": 5}, "count": 100},
        )
        assert ukf.eval_filter(metadata=KLOp.JSON(**{"user.role": "admin"}))
        assert not ukf.eval_filter(metadata=KLOp.JSON(**{"user.role": "guest"}))

    def test_json_with_comparison(self):
        """Test JSON operator with comparison operators."""
        ukf = BaseUKF(
            name="test",
            type="document",
            metadata={"count": 100, "nested": {"value": 50}},
        )
        assert ukf.eval_filter(metadata=KLOp.JSON(count=KLOp.GT(50)))
        assert not ukf.eval_filter(metadata=KLOp.JSON(count=KLOp.LT(50)))
        assert ukf.eval_filter(metadata=KLOp.JSON(**{"nested.value": KLOp.BETWEEN(0, 100)}))


class TestEvalFilterExistence:
    """Test field existence checks."""

    def test_field_exists(self):
        """Test checking if field exists (is not None)."""
        ukf = BaseUKF(name="test", type="document", description="test desc")
        assert ukf.eval_filter(description=None)

    def test_optional_field(self):
        """Test optional field existence."""
        ukf = BaseUKF(name="test", type="document", notes="some notes")
        assert ukf.eval_filter(notes=None)
