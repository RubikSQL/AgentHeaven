"""Unified filter builder for all KL backends.

This module provides a unified filter system that creates backend-agnostic
JSON intermediate representation (IR) which can be compiled to different
backend formats (SQL, Vector DB, MongoDB).

Architecture:
- Stage 1 (Shared): expr(**kwargs) creates JSON IR
- Stage 2 (Backend-Specific): Adapters compile JSON IR to target format
  - OrmFilterAdapter → SQLAlchemy (SQL)
  - VdbFilterAdapter → LlamaIndex MetadataFilters (Vector DB)
  - MdbFilterAdapter → MongoDB MQL (MongoDB)

Example:
    >>> # Stage 1: Create backend-agnostic JSON IR
    >>> expr = KLOp.expr(
    ...     priority=KLOp.BETWEEN(0, 100),
    ...     status=KLOp.IN(["active", "pending"])
    ... )
    >>> # Result: {'AND': [
    ...     {'FIELD:priority': {'AND': [{'>=': 0}, {'<=': 100}]}},
    ...     {'FIELD:status': {'OR': [{'IN': ['active', 'pending']}]}}
    ... ]}

    >>> # Stage 2: Compile to backend-specific format (via adapters)
    >>> # sql_clause = OrmFilterAdapter.parse(orms, expr)
    >>> # vdb_filters = VdbFilterAdapter.parse(expr)
    >>> # mql_query = MdbFilterAdapter.parse(expr)
"""

__all__ = [
    "KLOp",
]

from typing import Any, Dict, List, Optional, Union, Set, Tuple
import datetime
from dataclasses import dataclass


class _KLOp:
    """Base class for all filter operators.

    All filter operators inherit from this base class to provide
    a common interface for type checking and validation.
    """

    pass


# Standard operators (shared across all backends)
@dataclass
class _LIKE(_KLOp):
    """LIKE operator for pattern matching.

    In SQL: Uses SQL LIKE pattern (%, _)
    In Vector DB: Uses text_match
    In MongoDB: Converted to $regex
    """

    v: str


@dataclass
class _ILIKE(_KLOp):
    """ILIKE operator for case-insensitive pattern matching.

    In SQL: Uses SQL ILIKE pattern
    In Vector DB: Uses text_match_insensitive
    In MongoDB: Converted to $regex with 'i' option
    """

    v: str


@dataclass
class _BETWEEN(_KLOp):
    """BETWEEN operator for range queries.

    Converted to: field >= min AND field <= max
    """

    min: Optional[Union[int, float, datetime.datetime]] = None
    max: Optional[Union[int, float, datetime.datetime]] = None


@dataclass
class _LT(_KLOp):
    """Less than operator."""

    v: Union[int, float, datetime.datetime]


@dataclass
class _LTE(_KLOp):
    """Less than or equal operator."""

    v: Union[int, float, datetime.datetime]


@dataclass
class _GT(_KLOp):
    """Greater than operator."""

    v: Union[int, float, datetime.datetime]


@dataclass
class _GTE(_KLOp):
    """Greater than or equal operator."""

    v: Union[int, float, datetime.datetime]


@dataclass
class _AND(_KLOp):
    """AND operator for logical conjunction."""

    v: List[Any]


@dataclass
class _OR(_KLOp):
    """OR operator for logical disjunction."""

    v: List[Any]


@dataclass
class _NOT(_KLOp):
    """NOT operator for logical negation."""

    v: Any


@dataclass
class _NF(_KLOp):
    """NF (Normalized Form) operator for tags/auths queries.

    Used for querying normalized multi-valued fields like tags and auths.

    In SQL: Compiled to EXISTS subquery
    In Vector DB: Compiled to metadata filters
    In MongoDB: Compiled to $elemMatch

    Supports automatic conversion:
    - KLOp operators (GT, LT, BETWEEN, etc.) are automatically converted
    - Lists/sets/tuples are automatically converted to OR/IN operators

    Examples:
        >>> # Simple value
        >>> KLOp.expr(tags=KLOp.NF(slot="type", value="security"))

        >>> # Explicit OR
        >>> KLOp.expr(tags=KLOp.NF(slot="type", value=KLOp.OR(["security", "privacy"])))

        >>> # Implicit list-to-OR conversion
        >>> KLOp.expr(tags=KLOp.NF(slot="type", value=["security", "privacy"]))

        >>> # With other operators
        >>> KLOp.expr(tags=KLOp.NF(slot="priority", value=KLOp.BETWEEN(0, 100)))
    """

    v: Dict[str, Any]

    def __init__(self, **kwargs):
        self.v = dict()
        for key, value in kwargs.items():
            # Auto-convert operator values
            if hasattr(value, "__class__") and isinstance(value, _KLOp):
                self.v[key] = KLOp._expr(value)
            # Auto-convert lists to OR operator
            elif isinstance(value, (list, set, tuple)):
                self.v[key] = KLOp._expr(KLOp.OR(list(value)))
            else:
                self.v[key] = value


# MongoDB-specific operators (optional for other backends)
@dataclass
class _JSON(_KLOp):
    """JSON operator for nested field queries (MongoDB-specific).

    Uses dot notation to query nested fields in MongoDB documents.
    Supports value matching, comparison operators, and existence checks.
    Other backends may not support this operator.

    Use Cases:
        1. Single key-value matching:
            >>> KLOp.expr(metadata=KLOp.JSON(role="admin"))
            >>> # MongoDB: {"metadata.role": "admin"}

        2. Nested path with dot notation:
            >>> KLOp.expr(data=KLOp.JSON(**{"user.role": "admin"}))
            >>> # MongoDB: {"data.user.role": "admin"}

        3. With comparison operators:
            >>> KLOp.expr(metadata=KLOp.JSON(count=KLOp.GT(100)))
            >>> # MongoDB: {"metadata.count": {"$gt": 100}}

        4. Field existence check (value=...):
            >>> KLOp.expr(metadata=KLOp.JSON(email=...))
            >>> # MongoDB: {"metadata.email": {"$exists": true}}

        5. Field non-existence check (value=NOT(...)):
            >>> KLOp.expr(metadata=KLOp.JSON(optional=KLOp.NOT(...)))
            >>> # MongoDB: {"metadata.optional": {"$exists": false}}

        6. Multiple conditions (AND of all):
            >>> KLOp.expr(metadata=KLOp.JSON(type="categorical", status="active"))
            >>> # MongoDB: {"$and": [{"metadata.type": "categorical"}, {"metadata.status": "active"}]}

        7. Multiple conditions with operators:
            >>> KLOp.expr(metadata=KLOp.JSON(count=KLOp.GT(100), status=KLOp.IN(["active", "pending"])))
            >>> # MongoDB: {"$and": [{"metadata.count": {"$gt": 100}}, {"metadata.status": {"$in": ["active", "pending"]}}]}

        8. Implicit list-to-OR conversion:
            >>> KLOp.expr(metadata=KLOp.JSON(role=["admin", "superuser"]))
            >>> # MongoDB: {"metadata.role": {"$in": ["admin", "superuser"]}}
    """

    v: Dict[str, Any]

    def __init__(self, **kwargs):
        self.v = dict()
        for key, value in kwargs.items():
            # Auto-convert operator values
            if hasattr(value, "__class__") and isinstance(value, _KLOp):
                self.v[key] = KLOp._expr(value)
            # Auto-convert lists to OR operator
            elif isinstance(value, (list, set, tuple)):
                self.v[key] = KLOp._expr(KLOp.OR(list(value)))
            else:
                self.v[key] = value


class KLOp:
    """Unified filter builder for all KL backends.

    This class provides a two-stage architecture:
    1. expr(**kwargs) - Creates backend-agnostic JSON IR (shared)
    2. parse(expr) - Compiles JSON IR to backend format (via adapters)

    Supported backends:
    - SQL/SQLAlchemy (OrmFilterAdapter)
    - Vector DB/LlamaIndex (VdbFilterAdapter)
    - MongoDB/MQL (MdbFilterAdapter)

    The JSON IR format uses:
    - "FIELD:<name>" keys to indicate field context
    - Operator keys: "==", "!=", "<", "<=", ">", ">=", "LIKE", "ILIKE", "IN"
    - Logical operators: "AND", "OR", "NOT"
    - Special operators: "NF", "JSON"
    - None value: field existence check (MongoDB)

    Example:
        >>> # Create JSON IR
        >>> expr = KLOp.expr(
        ...     priority=KLOp.BETWEEN(0, 100),
        ...     status=KLOp.IN(["active", "pending"]),
        ...     description=KLOp.LIKE("%test%")
        ... )
        >>>
        >>> # Compile to backend-specific format (via adapters)
        >>> # sql_clause = OrmFilterAdapter.parse(orms, expr)
        >>> # vdb_filters = VdbFilterAdapter.parse(expr)
        >>> # mql_query = MdbFilterAdapter.parse(expr)
    """

    # Standard operator aliases (shared across all backends)
    LIKE = _LIKE
    ILIKE = _ILIKE
    BETWEEN = _BETWEEN
    LT = _LT
    LTE = _LTE
    GT = _GT
    GTE = _GTE
    AND = _AND
    OR = _OR
    NOT = _NOT
    IN = _OR  # Alias: IN is semantically OR
    NF = _NF
    JSON = _JSON

    @staticmethod
    def _is_value(value: Any) -> bool:
        """Check if a value is a simple value (not an operator or collection).

        Args:
            value: The value to check

        Returns:
            True if the value is a simple value, False otherwise

        Example:
            >>> KLOp._is_value(42)
            True
            >>> KLOp._is_value(KLOp.GT(42))
            False
            >>> KLOp._is_value([1, 2, 3])
            False
        """
        return not isinstance(value, (_KLOp, List, Set, Tuple, Dict))

    @staticmethod
    def _expr(value: Any) -> Any:
        """Parse a single value or expression into its JSON IR representation.

        This method recursively converts operator objects to JSON intermediate
        representation that is backend-agnostic.

        Args:
            value: The value or operator to parse

        Returns:
            Dictionary representing the parsed condition in JSON IR format

        Example:
            >>> KLOp._expr(KLOp.BETWEEN(0, 100))
            {'AND': [{'>=': 0}, {'<=': 100}]}

            >>> KLOp._expr(KLOp.NOT("test"))
            {'NOT': {'==': 'test'}}

            >>> KLOp._expr(KLOp.LIKE("%pattern%"))
            {'LIKE': '%pattern%'}
        """
        # Logical operators
        if isinstance(value, KLOp.NOT):
            return {"NOT": KLOp._expr(value.v)}

        if isinstance(value, KLOp.AND):
            return {"AND": [KLOp._expr(v) for v in value.v]}

        # OR/IN operators with mixed values
        if isinstance(value, (list, set)):
            values = [v for v in value if KLOp._is_value(v)]
            dicts = [d for d in value if isinstance(d, dict)]
            others = [o for o in value if not KLOp._is_value(o) and not isinstance(o, dict)]

            or_list = [KLOp._expr(v) for v in others]
            if values:
                or_list.append({"IN": values})
            if dicts:
                # Each dict in the list is treated as a separate AND group within the OR
                for d in dicts:
                    or_list.append(KLOp.expr(**d))
            return {"OR": or_list}

        if isinstance(value, (KLOp.IN, KLOp.OR)):
            values = [v for v in value.v if KLOp._is_value(v)]
            dicts = [d for d in value.v if isinstance(d, dict)]
            others = [o for o in value.v if not KLOp._is_value(o) and not isinstance(o, dict)]

            or_list = [KLOp._expr(v) for v in others]
            if values:
                or_list.append({"IN": values})
            if dicts:
                for d in dicts:
                    or_list.append(KLOp.expr(**d))
            return {"OR": or_list}

        # Range operators
        if isinstance(value, KLOp.BETWEEN):
            return {
                "AND": [
                    {">=": value.min if value.min is not None else float("-inf")},
                    {"<=": value.max if value.max is not None else float("inf")},
                ]
            }

        if isinstance(value, tuple):  # Shorthand for BETWEEN
            return {
                "AND": [
                    {">=": value[0] if value[0] is not None else float("-inf")},
                    {"<=": value[1] if value[1] is not None else float("inf")},
                ]
            }

        # Normalized form (tags/auths)
        if isinstance(value, KLOp.NF):
            return {"NF": value.v}

        # Pattern matching
        if isinstance(value, KLOp.LIKE):
            return {"LIKE": value.v}
        if isinstance(value, KLOp.ILIKE):
            return {"ILIKE": value.v}

        # Comparison operators
        if isinstance(value, KLOp.LT):
            return {"<": value.v}
        if isinstance(value, KLOp.LTE):
            return {"<=": value.v}
        if isinstance(value, KLOp.GT):
            return {">": value.v}
        if isinstance(value, KLOp.GTE):
            return {">=": value.v}

        # MongoDB-specific operators
        if isinstance(value, KLOp.JSON):
            return {"JSON": value.v}

        # Special handling for None: field existence check
        if value is None:
            return ...

        # Default: exact match
        return {"==": value}

    @staticmethod
    def expr(**kwargs) -> Dict[str, Any]:
        """Parse multiple filter conditions into a JSON filter structure.

        This is the main entry point for creating backend-agnostic filter
        expressions. The resulting JSON IR can be compiled to any backend
        format using the appropriate adapter.

        Args:
            **kwargs: Filter conditions as key-value pairs.

        Returns:
            Dictionary containing the parsed filter conditions in JSON IR format.
            Uses "FIELD:<name>" keys to indicate field context.

        Example:
            >>> # Simple conditions
            >>> KLOp.expr(status="active", priority=50)
            {'AND': [
                {'FIELD:status': {'==': 'active'}},
                {'FIELD:priority': {'==': 50}}
            ]}

            >>> # Complex conditions
            >>> KLOp.expr(
            ...     description=KLOp.NOT("def"),
            ...     version="v1.0.0",
            ...     priority=KLOp.BETWEEN(0, 100)
            ... )
            {
                'AND': [
                    {'FIELD:description': {'NOT': {'==': 'def'}}},
                    {'FIELD:version': {'==': 'v1.0.0'}},
                    {'FIELD:priority': {'AND': [{'>=': 0}, {'<=': 100}]}}
                ]
            }

            >>> # MongoDB-specific features
            >>> KLOp.expr(
            ...     metadata=KLOp.JSON(role="admin"),
            ...     tags=KLOp.NF(slot="type", value="security")
            ... )
            {
                'AND': [
                    {'FIELD:metadata': {'JSON': {'role': {'==': 'admin'}}}},
                    {'FIELD:tags': {'NF': {'slot': 'type', 'value': 'security'}}}
                ]
            }

            >>> # JSON with multiple fields (AND of all conditions)
            >>> KLOp.expr(
            ...     metadata=KLOp.JSON(type="categorical", status="active", count=KLOp.GT(100))
            ... )
            {
                'AND': [
                    {'FIELD:metadata': {'JSON': {
                        'type': {'==': 'categorical'},
                        'status': {'==': 'active'},
                        'count': {'>': 100}
                    }}}
                ]
            }
        """
        exprs = [{f"FIELD:{k}": KLOp._expr(v)} for k, v in kwargs.items()]
        return {"AND": exprs} if len(exprs) > 1 else (exprs[0] if exprs else None)
