"""
Tests for Vector DB compiler with empty OR/IN handling.
"""

import pytest
from ahvn.utils.klop import KLOp

# Check if LlamaIndex is available
try:
    from ahvn.utils.vdb.compiler import VectorCompiler
    from llama_index.core.vector_stores import MetadataFilters, MetadataFilter

    LLAMAINDEX_AVAILABLE = True
except ImportError:
    LLAMAINDEX_AVAILABLE = False
    pytest.skip("LlamaIndex not available", allow_module_level=True)


class TestEmptyORVectorDB:
    """Test empty OR/IN handling for Vector DB compiler."""

    def test_empty_or(self):
        """Test OR([]) compiles to never-match filter."""
        expr = KLOp.OR([])
        filters = VectorCompiler.compile(expr=KLOp._expr(expr))

        # Should return a filter that never matches
        assert filters is not None
        assert isinstance(filters, (MetadataFilters, MetadataFilter))

    def test_empty_and(self):
        """Test AND([]) compiles to match-all."""
        expr = KLOp.AND([])
        filters = VectorCompiler.compile(expr=KLOp._expr(expr))

        # Should be an empty AND filter (matches all - no conditions to satisfy)
        assert filters is not None
        assert isinstance(filters, MetadataFilters)
        assert filters.condition == "and"
        assert len(filters.filters) == 0

    def test_empty_in(self):
        """Test IN([]) compiles to never-match filter."""
        expr = KLOp.expr(status=KLOp.IN([]))
        filters = VectorCompiler.compile(expr=expr)

        # Should return a filter that never matches
        assert filters is not None
        assert isinstance(filters, (MetadataFilters, MetadataFilter))

    def test_normal_in(self):
        """Test IN with values compiles correctly."""
        expr = KLOp.expr(status=KLOp.IN(["active", "pending"]))
        filters = VectorCompiler.compile(expr=expr)

        # Should have OR filters for the values
        assert filters is not None
        assert isinstance(filters, MetadataFilters)
        # Should have filters for each value
        assert len(filters.filters) > 0

    def test_or_with_empty_in(self):
        """Test OR containing empty IN evaluates correctly."""
        # OR([status IN [], priority > 5])
        combined = {"OR": [{"FIELD:status": {"OR": []}}, {"FIELD:priority": {">": 5}}]}
        filters = VectorCompiler.compile(expr=combined)

        # Should compile successfully with the OR structure
        assert filters is not None
        assert isinstance(filters, MetadataFilters)
        # The compile wraps result in AND, but inner structure has OR with empty OR
        assert len(filters.filters) > 0

    def test_and_with_empty_in(self):
        """Test AND containing empty IN never matches."""
        # AND([status IN [], priority > 5])
        combined = {"AND": [{"FIELD:status": {"OR": []}}, {"FIELD:priority": {">": 5}}]}
        filters = VectorCompiler.compile(expr=combined)

        # Should have AND condition with impossible filter
        assert filters is not None
        assert isinstance(filters, MetadataFilters)
        assert filters.condition == "and"
        # Contains the nested structure with empty OR (impossible filter)
        assert len(filters.filters) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
