"""
MongoDB Query Language (MQL) Compiler for KLOp JSON IR.

This module provides functionality to compile KLOp JSON IR expressions
into MongoDB Query Language (MQL) for MongoDB backends.
"""

__all__ = ["MongoCompiler"]

from typing import Any, Dict, Optional, List
import re

from ..basic.log_utils import get_logger
from ..basic.debug_utils import error_str

logger = get_logger(__name__)


class MongoCompiler:
    """Compiler that converts KLOp JSON IR to MongoDB MQL."""

    @staticmethod
    def _parse_op(key: str, op: str, val: Any) -> Dict[str, Any]:
        """Build MQL expression for a specific operator.

        Args:
            key: Field name
            op: Operator type (==, !=, <, >, <=, >=, LIKE, ILIKE, IN)
            val: Value for the operator

        Returns:
            MongoDB query expression

        Raises:
            ValueError: If operator is unknown
        """
        if op == "==":
            return {key: val}
        elif op == "!=":
            return {key: {"$ne": val}}
        elif op == "<":
            return {key: {"$lt": val}}
        elif op == "<=":
            return {key: {"$lte": val}}
        elif op == ">":
            return {key: {"$gt": val}}
        elif op == ">=":
            return {key: {"$gte": val}}
        elif op == "LIKE":
            # Convert SQL LIKE pattern to MongoDB regex
            # First escape all regex special characters, then replace % and _
            # Extract % and _ positions first
            parts = []
            i = 0
            while i < len(val):
                if val[i] == "%":
                    parts.append(("wildcard_many", i))
                    i += 1
                elif val[i] == "_":
                    parts.append(("wildcard_one", i))
                    i += 1
                else:
                    # Find next wildcard
                    next_wildcard = len(val)
                    for j in range(i + 1, len(val)):
                        if val[j] in ("%", "_"):
                            next_wildcard = j
                            break
                    literal = val[i:next_wildcard]
                    parts.append(("literal", re.escape(literal)))
                    i = next_wildcard

            # Build regex from parts
            pattern = "".join(".*" if p[0] == "wildcard_many" else "." if p[0] == "wildcard_one" else p[1] for p in parts)
            return {key: {"$regex": pattern}}
        elif op == "ILIKE":
            # Case-insensitive LIKE - same logic as LIKE
            parts = []
            i = 0
            while i < len(val):
                if val[i] == "%":
                    parts.append(("wildcard_many", i))
                    i += 1
                elif val[i] == "_":
                    parts.append(("wildcard_one", i))
                    i += 1
                else:
                    next_wildcard = len(val)
                    for j in range(i + 1, len(val)):
                        if val[j] in ("%", "_"):
                            next_wildcard = j
                            break
                    literal = val[i:next_wildcard]
                    parts.append(("literal", re.escape(literal)))
                    i = next_wildcard

            pattern = "".join(".*" if p[0] == "wildcard_many" else "." if p[0] == "wildcard_one" else p[1] for p in parts)
            return {key: {"$regex": pattern, "$options": "i"}}
        elif op == "IN":
            if not isinstance(val, (list, tuple, set)):
                raise ValueError("IN operator requires a list, tuple, or set of values")
            return {key: {"$in": list(val)}}
        elif op == "NOT IN":
            if not isinstance(val, (list, tuple, set)):
                raise ValueError("NOT IN operator requires a list, tuple, or set of values")
            return {key: {"$nin": list(val)}}
        else:
            raise ValueError(f"Unknown/Incorrectly placed operator: '{op}'. " f"Supported operators: ==, !=, <, <=, >, >=, LIKE, ILIKE, IN, NOT IN")

    @staticmethod
    def _parse_nf(key: str, nf: Dict[str, Any]) -> Dict[str, Any]:
        """Build MQL expression for NF (normalized form) operator.

        NF operator is used for querying tags/auths arrays with slot-value pairs.
        In MongoDB, this translates to $elemMatch queries.

        Args:
            key: Field name (e.g., "tags", "auths")
            nf: Dictionary containing slot-value pairs

        Returns:
            MongoDB $elemMatch query

        Example:
            >>> _parse_nf("tags", {"slot": "type", "value": "security"})
            {"tags": {"$elemMatch": {"slot": "type", "value": "security"}}}
        """
        from ..klop import KLOp

        # Build $elemMatch query from NF dict
        elem_match = {}
        for nf_key, nf_val in nf.items():
            # Handle nested operators in NF values
            if isinstance(nf_val, dict):
                parsed = MongoCompiler._parse(field=nf_key, expr=nf_val)
                # Extract the actual condition from parsed result
                if nf_key in parsed:
                    elem_match[nf_key] = parsed[nf_key]
                else:
                    elem_match.update(parsed)
            else:
                elem_match[nf_key] = nf_val

        return {key: {"$elemMatch": elem_match}}

    @staticmethod
    def _parse_json(path: str, val: Any) -> Dict[str, Any]:
        """Build MQL expression for JSON path queries.

        Uses MongoDB dot notation to query nested fields.
        Supports value matching, operators, and existence checks.

        Args:
            path: Dot-notation path (e.g., "content_resources.type")
            val: Value to match. Can be:
                - Simple value: exact match
                - Operator dict: comparison/pattern matching
                - Ellipsis (...): field existence check ({"$exists": true})
                - {"NOT": ...}: field non-existence check ({"$exists": false})

        Returns:
            MongoDB query with dot notation

        Examples:
            >>> _parse_json("content_resources.type", "categorical")
            {"content_resources.type": "categorical"}
            >>> _parse_json("content_resources.n_records", {">": 100})
            {"content_resources.n_records": {"$gt": 100}}
            >>> _parse_json("user.email", ...)
            {"user.email": {"$exists": true}}
            >>> _parse_json("optional", {"NOT": ...})
            {"optional": {"$exists": false}}
        """
        # Handle Ellipsis: existence check
        if val is ...:
            return {path: {"$exists": True}}

        # Handle None: also means existence check (for backward compatibility)
        if val is None:
            return {path: {"$exists": True}}

        # If val is a dict, it might be an operator expression
        if isinstance(val, dict) and len(val) == 1:
            op, op_val = next(iter(val.items()))

            # Handle NOT(...) or NOT(EXISTS) for non-existence check
            if op == "NOT":
                # If NOT contains EXISTS or Ellipsis
                if op_val is ...:
                    return {path: {"$exists": False}}
                # Handle NOT({"==": ...}) - unwrap the inner operator
                if isinstance(op_val, dict) and "==" in op_val and op_val["=="] is ...:
                    return {path: {"$exists": False}}
                if isinstance(op_val, dict) and "EXISTS" in op_val:
                    # Invert the EXISTS value
                    return {path: {"$exists": not op_val["EXISTS"]}}

            # Handle comparison operators
            if op in ("==", "!=", "<", "<=", ">", ">=", "IN", "NOT IN", "LIKE", "ILIKE"):
                parsed = MongoCompiler._parse_op(path, op, op_val)
                return parsed

            # Handle EXISTS operator (for backward compatibility)
            if op == "EXISTS":
                return {path: {"$exists": op_val}}

        # Otherwise, simple value match
        return {path: val}

    def _parse(field: Optional[str] = None, expr: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Recursively build MongoDB MQL from filter nodes.

        Args:
            field: Current field context for operator expressions
            expr: The filter expression dictionary to parse

        Returns:
            MongoDB query expression

        Raises:
            ValueError: If the expr structure is invalid
        """
        if not expr:
            return {}

        # Handle ellipsis for field existence check
        if expr is ...:
            if field is None:
                raise ValueError("Ellipsis (...) requires a field context (FIELD:).")
            return {field: {"$exists": True}}

        if len(expr) > 1:
            raise NotImplementedError("Complex expressions with multiple root keys not supported.")

        op, val = next(iter(expr.items()))
        try:
            if op == "AND":
                exprs = [MongoCompiler._parse(field=field, expr=v) for v in val]
                exprs = [expr for expr in exprs if expr]
                if not exprs:
                    return {}
                if len(exprs) == 1:
                    return exprs[0]
                return {"$and": exprs}

            if op == "OR":
                exprs = [MongoCompiler._parse(field=field, expr=v) for v in val]
                exprs = [expr for expr in exprs if expr]
                if not exprs:
                    return {"$literal": False}
                if len(exprs) == 1:
                    return exprs[0]
                return {"$or": exprs}

            if op == "NOT":
                inner_expr = val
                # Handle KLOp object by extracting its expression
                if hasattr(inner_expr, "expr"):
                    inner_expr = inner_expr.expr

                # Special case: NOT({"==": ...}) should be treated as non-existence check
                if isinstance(inner_expr, dict) and "==" in inner_expr and inner_expr["=="] is ...:
                    if field is None:
                        raise ValueError("NOT(...) requires a field context.")
                    return {field: {"$exists": False}}

                inner = MongoCompiler._parse(field=field, expr=inner_expr)
                if not inner:
                    return {}
                # Special handling for $exists: NOT($exists: true) → $exists: false
                if len(inner) == 1:
                    key, cond = next(iter(inner.items()))
                    if isinstance(cond, dict):
                        # Check if it's an $exists operation
                        if "$exists" in cond and len(cond) == 1:
                            # Invert the exists value
                            return {key: {"$exists": not cond["$exists"]}}
                        return {key: {"$not": cond}}
                    else:
                        # Check if the condition value is Ellipsis (existence check)
                        if cond is ...:
                            return {key: {"$exists": False}}
                        return {key: {"$ne": cond}}
                return {"$nor": [inner]}

            if op.startswith("FIELD:"):
                if field is not None:
                    raise ValueError(f"Nested FIELD: {op} inside {field} not allowed.")
                return MongoCompiler._parse(field=op.split("FIELD:")[1], expr=val)

            if op == "NF":
                if field is None:
                    raise ValueError("NF operator requires a field context (FIELD:).")
                return MongoCompiler._parse_nf(field, val)

            if op == "JSON":
                # JSON operator: {"JSON": {key1: value1, key2: value2, ...}}
                # Similar to NF but for nested JSON field queries with dot notation

                if field is None:
                    raise ValueError("JSON operator requires a field context (FIELD:).")

                if not isinstance(val, dict):
                    raise ValueError("JSON operator requires a dict value")

                # Build AND expression for all key-value pairs
                conditions = []
                for json_key, json_val in val.items():
                    full_path = f"{field}.{json_key}"

                    # Handle Ellipsis - existence check
                    if json_val is ...:
                        condition = {full_path: {"$exists": True}}
                    # If json_val is a dict (already parsed expression), parse it with field context
                    elif isinstance(json_val, dict):
                        condition = MongoCompiler._parse(field=full_path, expr=json_val)
                    else:
                        # Simple value - create direct field match
                        condition = {full_path: json_val}

                    if condition:
                        conditions.append(condition)

                if not conditions:
                    return {}
                if len(conditions) == 1:
                    return conditions[0]
                return {"$and": conditions}

            if op == "EXISTS":
                # EXISTS operator for field existence checks
                # Now primarily generated from None values
                if field is None:
                    raise ValueError("EXISTS operator requires a field context (FIELD:).")
                return {field: {"$exists": val}}

            if field is None:
                raise ValueError(f"Operator '{op}' requires a field context (FIELD:).")

            return MongoCompiler._parse_op(field, op, val)

        except Exception as e:
            raise ValueError(f"Error processing expression key '{op}'.\n{expr}\n{error_str(e)}")

    @staticmethod
    def compile(expr: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """Convert a KLOp JSON IR to MongoDB MQL.

        Args:
            expr: The parsed filter expression dictionary (optional)
            **kwargs: Filter conditions as key-value pairs

        Returns:
            MongoDB query expression

        Raises:
            ValueError: If filter structure is invalid
        """
        from ..klop import KLOp

        exprs = []
        if expr:
            parsed = MongoCompiler._parse(expr=expr)
            if parsed:
                exprs.append(parsed)
        if kwargs:
            parsed = MongoCompiler._parse(expr=KLOp.expr(**kwargs))
            if parsed:
                exprs.append(parsed)

        if not exprs:
            return {}
        if len(exprs) == 1:
            return exprs[0]
        return {"$and": exprs}
