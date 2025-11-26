"""
SQL Compiler for KLOp JSON IR.

This module provides functionality to compile KLOp JSON IR expressions
into SQLAlchemy query expressions for database backends.
"""

from __future__ import annotations

__all__ = ["SQLCompiler"]

from typing import Any, Dict, Optional, TYPE_CHECKING

from ..basic.log_utils import get_logger
from ..basic.debug_utils import error_str
from ..deps import deps

if TYPE_CHECKING:
    from sqlalchemy.sql.elements import ClauseElement


def get_sa():
    return deps.load("sqlalchemy")


def get_sa_elements():
    return deps.load("sqlalchemy.sql.elements")


logger = get_logger(__name__)


class SQLCompiler:
    """Compiler that converts KLOp JSON IR to SQLAlchemy expressions."""

    @staticmethod
    def _parse_op(orms: Dict[str, Any], entity: str, key: str, op: str, val: Any) -> ClauseElement:
        """Build expression for a specific operator.

        Args:
            orms: Mapping of entity names to SQLAlchemy model classes
            entity: The current entity name for dimension mapping
            key: Current field context for operator expressions
            op: Operator type (==, !=, <, >, <=, >=, LIKE, ILIKE, IN)
            val: Value for the operator

        Returns:
            SQLAlchemy expression for the operator

        Raises:
            ValueError: If field is None or operator is unknown
        """
        attr = getattr(orms[entity], orms[entity].alias(key))
        if op == "==":
            return attr == val
        elif op == "!=":
            return attr != val
        elif op == "<":
            return attr < val
        elif op == "<=":
            return attr <= val
        elif op == ">":
            return attr > val
        elif op == ">=":
            return attr >= val
        elif op == "LIKE":
            return attr.like(str(val))
        elif op == "ILIKE":
            return attr.ilike(str(val))
        elif op == "IN":
            if not isinstance(val, (list, tuple, set)):
                raise ValueError("IN operator requires a list, tuple, or set of values")
            return attr.in_([v for v in val])
        else:
            raise ValueError(f"Unknown/Incorrectly placed operator: '{op}'. " f"Supported operators: ==, !=, <, <=, >, >=, LIKE, ILIKE, IN")

    @staticmethod
    def _parse_nf(orms: Dict[str, Any], entity: str, nf_entity: str, nf: Dict[str, Any]) -> ClauseElement:
        """Build expression for NF (normalized form) operator.

        Args:
            orms: Mapping of entity names to SQLAlchemy model classes
            entity: The current entity name for dimension mapping
            nf_entity: The entity name for the NF check (dimension table)
            nf: Dictionary containing NF attributes and their values
                Values can be simple values or nested operators (dict)

        Returns:
            SQLAlchemy expression for the NF operator

        Example:
            >>> # Basic NF: {"slot": "TOPIC", "value": "math"}
            >>> # NF with LIKE: {"slot": "TOPIC", "value": {"LIKE": "%math%"}}
        """
        # Build WHERE conditions for dimension table
        # Each nf key-value pair becomes a condition
        conditions = []
        for nf_key, nf_val in nf.items():
            # Handle nested operators in NF values (e.g., LIKE, GT, etc.)
            if isinstance(nf_val, dict):
                # Recursively parse nested operator
                parsed = SQLCompiler._parse(orms=orms, entity=nf_entity, field=nf_key, expr=nf_val)
                conditions.append(parsed)
            else:
                # Simple equality check
                # Use alias() to handle reserved field names (e.g., "value" -> "value_")
                attr = getattr(orms[nf_entity], orms[nf_entity].alias(nf_key))
                conditions.append(attr == nf_val)

        return get_sa().exists(
            get_sa()
            .select(get_sa().distinct(orms[nf_entity].id))
            .where(
                orms[entity].id == orms[nf_entity].ukf_id,
                *conditions,
            )
        )

    @staticmethod
    def _parse_json(orms: Dict[str, Any], entity: str, field: str, path: str, val: Any) -> ClauseElement:
        """Build expression for JSON path queries.

        Uses database-specific JSON operators to query nested fields.
        Supports PostgreSQL JSONB, DuckDB JSON, and other JSON-capable databases.

        Args:
            orms: Mapping of entity names to SQLAlchemy model classes
            entity: The current entity name for dimension mapping
            field: The JSON column name (e.g., "content_resources")
            path: Dot-notation path within JSON (e.g., "stats.views")
            val: Value to match. Can be:
                - Simple value: exact match
                - Operator dict: comparison/pattern matching
                - Ellipsis (...): field existence check
                - {"NOT": ...}: field non-existence check

        Returns:
            SQLAlchemy expression for JSON queries

        Examples:
            PostgreSQL JSONB:
                            # Comparison: content_resources->'stats'->>'views' > 2000
            if isinstance(val, dict) and len(val) == 1:
                op, op_val = next(iter(val.items()))

                # Build path expression with proper type handling
                path_expr = attr
                for part in path_parts[:-1]:
                    path_expr = path_expr.op("->")(literal(part))
                path_expr = path_expr.op("->>")(literal(path_parts[-1]))
                content_resources @> '{"type": "categorical"}'
            DuckDB JSON:
                json_extract(content_resources, '$.stats.views') > 2000
        """
        from sqlalchemy import cast, String, Integer, Float, Boolean, literal
        from sqlalchemy.dialects import postgresql

        attr = getattr(orms[entity], orms[entity].alias(field))

        # Convert dot notation to path array: "stats.views" -> ["stats", "views"]
        path_parts = path.split(".")

        # Handle Ellipsis: existence check
        if val is ...:
            # PostgreSQL: content_resources ? 'key' or content_resources #> '{path}' IS NOT NULL
            # DuckDB: json_extract(...) IS NOT NULL
            if path_parts:
                # Build path expression and check if it's not null
                path_expr = attr
                for part in path_parts[:-1]:
                    path_expr = path_expr.op("->")(part)
                path_expr = path_expr.op("->>")(path_parts[-1])
                return path_expr.isnot(None)
            else:
                return attr.isnot(None)

        # Handle value matching
        if isinstance(val, dict) and len(val) == 1:
            op, op_val = next(iter(val.items()))

            # Handle NOT(...) for non-existence check
            if op == "NOT":
                if op_val is ...:
                    # Field non-existence: IS NULL
                    path_expr = attr
                    for part in path_parts[:-1]:
                        path_expr = path_expr.op("->")(literal(part))
                    path_expr = path_expr.op("->>")(literal(path_parts[-1]))
                    return path_expr.is_(None)

                # NOT(value) - negation of the inner expression
                inner = SQLCompiler._parse_json(orms, entity, field, path, op_val)
                return get_sa().not_(inner)

            # Handle comparison operators
            if op in ("==", "!=", "<", "<=", ">", ">=", "LIKE", "ILIKE", "IN"):
                # Extract the value at path as text, then cast if needed
                path_expr = attr
                for part in path_parts[:-1]:
                    path_expr = path_expr.op("->")(literal(part))
                path_expr = path_expr.op("->>")(literal(path_parts[-1]))  # ->> extracts as text

                # Cast based on value type for comparisons
                if op in (">", ">=", "<", "<="):
                    if isinstance(op_val, int):
                        path_expr = cast(path_expr, Integer)
                    elif isinstance(op_val, float):
                        path_expr = cast(path_expr, Float)

                # Apply operator
                if op == "==":
                    return path_expr == str(op_val) if not isinstance(op_val, (int, float)) else path_expr == op_val
                elif op == "!=":
                    return path_expr != str(op_val) if not isinstance(op_val, (int, float)) else path_expr != op_val
                elif op == "<":
                    return path_expr < op_val
                elif op == "<=":
                    return path_expr <= op_val
                elif op == ">":
                    return path_expr > op_val
                elif op == ">=":
                    return path_expr >= op_val
                elif op == "LIKE":
                    return path_expr.like(str(op_val))
                elif op == "ILIKE":
                    return path_expr.ilike(str(op_val))
                elif op == "IN":
                    # For IN, compare text values
                    return path_expr.in_([str(v) for v in op_val])

            # Handle AND/OR for complex nested expressions
            if op == "AND":
                exprs = [SQLCompiler._parse_json(orms, entity, field, path, v) for v in op_val]
                exprs = [expr for expr in exprs if expr is not None]
                return get_sa().and_(*exprs) if exprs else None
            if op == "OR":
                exprs = [SQLCompiler._parse_json(orms, entity, field, path, v) for v in op_val]
                exprs = [expr for expr in exprs if expr is not None]
                return get_sa().or_(*exprs) if exprs else None

        # Simple value match: content_resources->>'path' = 'value'
        path_expr = attr
        for part in path_parts[:-1]:
            path_expr = path_expr.op("->")(literal(part))
        path_expr = path_expr.op("->>")(literal(path_parts[-1]))

        # Cast booleans to strings for comparison
        if isinstance(val, bool):
            val_str = "true" if val else "false"
            return path_expr == val_str

        return path_expr == str(val) if not isinstance(val, (int, float)) else cast(path_expr, type(val).__name__) == val

    @staticmethod
    def _parse(
        orms: Dict[str, Any],
        entity: str = "main",
        field: Optional[str] = None,
        expr: Dict[str, Any] = None,
    ) -> ClauseElement:
        """Recursively build SQLAlchemy expressions from filter nodes.

        Args:
            orms: Mapping of entity names to SQLAlchemy model classes
            entity: The current entity name for dimension mapping
            field: Current field context for operator expressions
            expr: The filter expression dictionary to parse

        Returns:
            SQLAlchemy expression object or None if no valid expression

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
                exprs = [SQLCompiler._parse(orms=orms, entity=entity, field=field, expr=v) for v in val]
                exprs = [expr for expr in exprs if expr is not None]
                if len(exprs) == 0:
                    # AND([]) = TRUE (all zero conditions satisfied) -> no filter
                    # OR([]) = FALSE (none of zero alternatives true) -> always false
                    if op == "AND":
                        return None  # No filter = match all
                    else:  # OR
                        # Return a condition that's always false
                        return get_sa().literal(False)
                if len(exprs) == 1:
                    return exprs[0]
                return get_sa().and_(*exprs) if op == "AND" else get_sa().or_(*exprs)

            if op == "NOT":
                return get_sa().not_(SQLCompiler._parse(orms=orms, entity=entity, field=field, expr=val))

            if op.startswith("FIELD:"):
                if field is not None:
                    raise ValueError(f"Nested FIELD: {op} inside {field} not allowed.")
                return SQLCompiler._parse(orms=orms, entity=entity, field=op.split("FIELD:")[1], expr=val)

            if op == "NF":
                return SQLCompiler._parse_nf(orms=orms, entity=entity, nf_entity=field, nf=val)

            if op == "JSON":
                # JSON operator: {"JSON": {key1: value1, key2: value2, ...}}
                # Similar to NF but for nested JSON field queries
                if field is None:
                    raise ValueError("JSON operator requires a field context (FIELD:).")

                if not isinstance(val, dict):
                    raise ValueError("JSON operator requires a dict value")

                # Build AND expression for all key-value pairs
                conditions = []
                for json_key, json_val in val.items():
                    # Use _parse_json for each key-value pair
                    # json_val could be a simple value, Ellipsis, or a parsed expression dict
                    condition = SQLCompiler._parse_json(orms=orms, entity=entity, field=field, path=json_key, val=json_val)

                    if condition is not None:
                        conditions.append(condition)

                if not conditions:
                    return None
                if len(conditions) == 1:
                    return conditions[0]
                return get_sa().and_(*conditions)

            if field is None:
                raise ValueError(f"Operator '{op}' requires a field context (FIELD:).")

            return SQLCompiler._parse_op(orms=orms, entity=entity, key=field, op=op, val=val)
        except Exception as e:
            raise ValueError(f"Error processing expression key '{op}'.\n{expr}\n{error_str(e)}")

    @staticmethod
    def compile(
        orms: Dict[str, Any],
        expr: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> ClauseElement:
        """Convert a KLOp JSON IR to SQLAlchemy query expressions.

        Args:
            orms: Mapping of entity names to SQLAlchemy model classes
            expr: The parsed filter expression dictionary (optional)
            **kwargs: Filter conditions as key-value pairs

        Returns:
            SQLAlchemy expression object or None

        Raises:
            ValueError: If filter structure is invalid
        """
        from ..klop import KLOp

        exprs = list()
        if expr:
            exprs.append(SQLCompiler._parse(orms=orms, expr=expr))
        if kwargs:
            exprs.append(SQLCompiler._parse(orms=orms, expr=KLOp.expr(**kwargs)))

        if len(exprs) == 0:
            return None
        if len(exprs) == 1:
            return exprs[0]
        return get_sa().and_(*exprs)
