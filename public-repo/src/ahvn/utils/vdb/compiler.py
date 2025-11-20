"""
Vector Filter Compiler for KLOp JSON IR.

This module provides functionality to compile KLOp JSON IR expressions
into LlamaIndex MetadataFilters for vector database backends.
"""

__all__ = ["VectorCompiler"]

from typing import Any, Dict, Optional, Union

try:
    from llama_index.core.vector_stores import (
        MetadataFilters,
        MetadataFilter,
        ExactMatchFilter,
    )

    LLAMAINDEX_AVAILABLE = True
except ImportError:
    LLAMAINDEX_AVAILABLE = False
    MetadataFilters = None
    MetadataFilter = None
    ExactMatchFilter = None

from ..basic.log_utils import get_logger
from ..basic.debug_utils import error_str

logger = get_logger(__name__)


class VectorCompiler:
    """Compiler that converts KLOp JSON IR to LlamaIndex filters."""

    @staticmethod
    def _to_filters(*expr_filters, op="and") -> "MetadataFilters":
        """Combine multiple filter expressions into MetadataFilters.

        Args:
            *expr_filters: Variable number of filter expressions
            op: Logical operator ("and" or "or")

        Returns:
            MetadataFilters object combining all filters
        """
        normalized = []
        for expr_filter in expr_filters:
            if expr_filter is None:
                continue
            if isinstance(expr_filter, (list, tuple, set)):
                # Recursively convert list elements and add each to normalized
                for item in expr_filter:
                    if item is not None:
                        if isinstance(item, (MetadataFilter, ExactMatchFilter, MetadataFilters)):
                            normalized.append(item)
            elif isinstance(expr_filter, MetadataFilters):
                normalized.append(expr_filter)
            elif isinstance(expr_filter, (ExactMatchFilter, MetadataFilter)):
                normalized.append(expr_filter)
            elif isinstance(expr_filter, dict):
                continue
        return MetadataFilters(filters=normalized, condition=op)

    @staticmethod
    def _parse_op(key: str, op: str, val: Any) -> Union["MetadataFilter", "MetadataFilters"]:
        """Build LlamaIndex filter expression for a specific operator.

        Args:
            key: Metadata field key
            op: Operator type (==, !=, <, >, <=, >=, LIKE, ILIKE, IN)
            val: Value for the operator

        Returns:
            LlamaIndex filter object

        Raises:
            ValueError: If operator is unknown
        """
        if op == "==":
            return ExactMatchFilter(key=key, value=val)
        if op == "IN":
            if not isinstance(val, (list, tuple, set)):
                raise ValueError("IN operator requires a list, tuple, or set of values")
            return VectorCompiler._to_filters([ExactMatchFilter(key=key, value=v) for v in val], op="or")

        llama_op = {
            "==": "==",
            "!=": "!=",
            "<": "<",
            "<=": "<=",
            ">": ">",
            ">=": ">=",
            "LIKE": "text_match",
            "ILIKE": "text_match_insensitive",
            "IN": "in",
        }.get(op, "in")
        return MetadataFilter(key=key, value=val, operator=llama_op)

    @staticmethod
    def _parse(field: Optional[str] = None, expr: Optional[Dict[str, Any]] = None) -> Optional[Union["MetadataFilter", "MetadataFilters"]]:
        """Recursively build LlamaIndex filter objects from filter nodes.

        Args:
            field: Current field context for operator expressions
            expr: The filter expression dictionary to parse

        Returns:
            LlamaIndex filter object or None

        Raises:
            ValueError: If the expr structure is invalid
        """
        if not expr:
            return None
        if len(expr) > 1:
            raise NotImplementedError("Complex expressions with multiple root keys not supported.")

        op, val = next(iter(expr.items()))
        try:
            if op in ("AND", "OR"):
                exprs = [VectorCompiler._parse(field=field, expr=v) for v in val]
                exprs = [expr for expr in exprs if expr is not None]
                if not exprs:
                    # AND([]) = TRUE (all zero conditions satisfied) -> no filter
                    # OR([]) = FALSE (none of zero alternatives true) -> empty OR filter (never matches)
                    if op == "AND":
                        return None  # No filter = match all
                    else:  # OR
                        # Return an empty OR filter which never matches (no alternatives)
                        return MetadataFilters(filters=[], condition="or")
                return VectorCompiler._to_filters(*exprs, op=op.lower())

            if op == "NOT":
                return MetadataFilters(
                    filters=[VectorCompiler._parse(field=field, expr=val)],
                    condition="not",
                )

            if op.startswith("FIELD:"):
                if field is not None:
                    raise ValueError(f"Nested FIELD: {op} inside {field} not allowed.")
                return VectorCompiler._parse(field=op.split("FIELD:")[1], expr=val)

            if field is None:
                raise ValueError(f"Operator '{op}' requires a field context (FIELD:).")

            return VectorCompiler._parse_op(field, op, val)
        except Exception as e:
            raise ValueError(f"Error processing expression key '{op}'.\n{expr}\n{error_str(e)}")

    @staticmethod
    def compile(expr: Optional[Dict[str, Any]] = None, **kwargs) -> Optional["MetadataFilters"]:
        """Convert a KLOp JSON IR to LlamaIndex MetadataFilters.

        Args:
            expr: The parsed filter expression dictionary (optional)
            **kwargs: Filter conditions as key-value pairs

        Returns:
            LlamaIndex MetadataFilters object or None

        Raises:
            ImportError: If LlamaIndex is not available
            ValueError: If filter structure is invalid
        """
        if not LLAMAINDEX_AVAILABLE:
            raise ImportError("LlamaIndex is required for vector compilation. " "Install it with: pip install llama-index-core")

        from ..klop import KLOp

        exprs = list()
        if expr:
            exprs.append(VectorCompiler._parse(expr=expr))
        if kwargs:
            exprs.append(VectorCompiler._parse(expr=KLOp.expr(**kwargs)))

        if not exprs:
            return None
        return VectorCompiler._to_filters(*exprs)
