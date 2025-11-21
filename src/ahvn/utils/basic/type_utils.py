__all__ = [
    "autotype",
    "jsonschema_type",
    "parse_function_signature",
]

from typing import Any, Optional, Dict, List
import ast
import inspect
import json


def autotype(obj: str) -> Any:
    """Automatically convert a string to its appropriate Python type.

    Tries to parse the string as different types in order of precedence:
    integer → float → boolean → None → JSON → JSON lines → Python expression → string

    This is useful for parsing configuration values, command line arguments,
    or user input where the type should be inferred from the string format.

    Warning: evaluates Python expressions using eval(), which can be dangerous.
    Use with caution and only with controlled input sources.

    Args:
        obj: The string to convert to an appropriate type.

    Returns:
        The converted object. If no conversion is possible, returns the original string.

    Examples:
        >>> autotype("42")
        42
        >>> type(autotype("42"))
        <class 'int'>

        >>> autotype("3.14")
        3.14
        >>> type(autotype("3.14"))
        <class 'float'>

        >>> autotype("true")
        True
        >>> autotype("false")
        False

        >>> autotype("none")
        None
        >>> autotype("null")
        None

        >>> autotype("'hello'")  # Quoted strings remain as strings
        'hello'
        >>> autotype('"world"')
        'world'

        >>> autotype('{"key": "value"}')  # JSON parsing
        {'key': 'value'}
        >>> autotype("[1, 2, 3]")
        [1, 2, 3]

        >>> autotype("1 + 2")  # Expression evaluation
        3

        >>> autotype("Hello, World!")  # Fallback to string
        'Hello, World!'

    Warning:
        Uses eval() for expression evaluation, which can be dangerous with untrusted input.
        Use with caution and only with controlled input sources.
    """
    obj = str(obj)
    if obj == "":
        return ""
    if not obj.strip():
        return obj
    try:
        return int(obj)
    except ValueError:
        pass
    try:
        return float(obj)
    except ValueError:
        pass
    if obj.lower().strip() in ("true", "false"):
        return obj.lower().strip() == "true"
    if obj.lower().strip() == "none":
        return None
    try:
        return json.loads(obj)
    except json.JSONDecodeError:
        pass
    try:
        return [json.loads(line) for line in obj.strip().splitlines() if line.strip()]
    except json.JSONDecodeError:
        pass
    try:
        return eval(obj)  # unsafe
    except Exception:
        pass
    return obj


def jsonschema_type(type_annotation: Optional[str]) -> Dict[str, Any]:
    """Convert a Python type annotation string to JSON schema format.

    This is the main function for converting Python type annotations to JSON schemas.
    It handles complex types including generics, unions, literals, and optional types.

    Args:
        type_annotation: A Python type annotation string (e.g., "int", "List[str]",
                        "Optional[Dict[str, int]]", "Literal['fast', 'slow']").

    Returns:
        A JSON schema dictionary. Examples:

        >>> jsonschema_type("int")
        {'type': 'integer'}

        >>> jsonschema_type("List[str]")
        {'type': 'array', 'items': {'type': 'string'}}

        >>> jsonschema_type("Optional[str]")
        {'type': 'string'}

        >>> jsonschema_type("Union[str, int]")
        {'type': 'string', 'x-original-union': ['str', 'int']}

        >>> jsonschema_type("Literal['fast', 'slow']")
        {'type': 'string', 'enum': ['fast', 'slow']}

        >>> jsonschema_type("datetime")
        {'type': 'string', 'format': 'date-time'}

        >>> jsonschema_type("CustomType")
        {'type': 'string', 'x-original-type': 'CustomType'}

        >>> jsonschema_type("")
        {}

    Note:
        Unknown or complex types are typically converted to {'type': 'string'}
        with additional metadata stored in x-original-* fields for debugging.
    """
    if not type_annotation:
        return {}

    original = type_annotation.strip()
    if not original:
        return {}

    return _normalize_type(original)


def parse_function_signature(func: callable) -> Dict[str, Any]:
    """Extract type information and defaults from a Python function signature.

    This function analyzes a function's signature and docstring to extract
    comprehensive type information, default values, and parameter metadata.
    It combines signature inspection with docstring parsing for complete information.

    Args:
        func: The Python function to analyze.

    Returns:
        A dictionary containing parameter information with the following structure:

        >>> def example_func(a: int, b: str = "default", c: Optional[float] = None) -> bool:
        ...     '''Example function.
        ...
        ...     Args:
        ...         a (int): First parameter.
        ...         b (str, optional): Second parameter. Defaults to "default".
        ...         c (Optional[float], optional): Third parameter. Defaults to None.
        ...     '''
        ...     return True
        >>>
        >>> result = parse_function_signature(example_func)
        >>> result['parameters']['a']['type']
        'integer'
        >>> result['parameters']['a']['required']
        True
        >>> result['parameters']['b']['type']
        'string'
        >>> result['parameters']['b']['default']
        'default'
        >>> result['parameters']['b']['required']
        False
        >>> result['return_type']
        {'type': 'boolean'}

    The returned dictionary has these keys:
        - 'parameters': Dict mapping parameter names to their schema info
        - 'return_type': JSON schema for the return type
        - 'has_var_args': Boolean indicating if *args present
        - 'has_var_kwargs': Boolean indicating if **kwargs present

    Note:
        This only analyzes the function signature - for full docstring parsing
        including descriptions, use parse_docstring() from func_utils.
    """
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return {}

    parameters = {}
    has_var_args = False
    has_var_kwargs = False

    for param_name, param in signature.parameters.items():
        param_info = {
            "required": param.default is inspect._empty,
            "default": param.default if param.default is not inspect._empty else None,
        }

        # Handle parameter kind
        if param.kind == param.VAR_POSITIONAL:
            has_var_args = True
            continue
        elif param.kind == param.VAR_KEYWORD:
            has_var_kwargs = True
            continue
        elif param.kind == param.KEYWORD_ONLY:
            param_info["keyword_only"] = True
        elif param.kind == param.POSITIONAL_ONLY:
            param_info["positional_only"] = True

        # Extract type annotation
        if param.annotation is not inspect._empty:
            param_info["annotation"] = _get_type_string(param.annotation)
            param_info["type_schema"] = jsonschema_type(param_info["annotation"])
        else:
            param_info["type_schema"] = {"type": "string"}  # Default fallback

        # Coerce default value to appropriate type
        if param.default is not inspect._empty:
            param_info["default"] = _coerce_default_value(param.default, param_info["type_schema"])

        parameters[param_name] = param_info

    # Handle return type
    return_type_schema = {"type": "string"}  # Default fallback
    if signature.return_annotation is not inspect._empty:
        return_annotation = _get_type_string(signature.return_annotation)
        return_type_schema = jsonschema_type(return_annotation)

    return {
        "parameters": parameters,
        "return_type": return_type_schema,
        "has_var_args": has_var_args,
        "has_var_kwargs": has_var_kwargs,
    }


# ===== Internal Implementation Functions =====


def _get_type_string(annotation) -> str:
    """Get string representation of a type annotation."""
    if hasattr(annotation, "__name__"):
        return annotation.__name__
    return str(annotation)


def _infer_json_type(value: Any) -> Optional[str]:
    """Infer JSON schema type from a Python value."""
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if value is None:
        return "null"
    return None


def _strip_quotes(value: str) -> str:
    """Strip surrounding quotes from a string value."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _coerce_default_value(value: Any, type_schema: Dict[str, Any]) -> Any:
    """Coerce a default value to the appropriate type based on schema."""
    if isinstance(value, (int, float, bool, str)) or value is None:
        return value
    return value  # Return as-is for complex types


def _literal_values_from_inner(inner: str) -> List[Any]:
    """Extract literal values from a type annotation string."""
    try:
        parsed = ast.literal_eval(f"({inner},)")
    except (SyntaxError, ValueError):
        return [_strip_quotes(part.strip()) for part in inner.split(",") if part.strip()]
    if isinstance(parsed, tuple):
        return list(parsed)
    return [parsed]


def _normalize_literal_type(inner: str, original: str) -> Optional[Dict[str, Any]]:
    """Normalize a Literal type to JSON schema format."""
    values = _literal_values_from_inner(inner)
    if not values:
        return None

    inferred_type: Optional[str] = None
    normalized_values: List[Any] = []

    for value in values:
        json_type = _infer_json_type(value)
        if json_type is None:
            return {
                "type": "string",
                "enum": [str(item) for item in values],
                "x-original-type": original,
            }
        if json_type == "null":
            if len(values) > 1:
                return {
                    "type": "string",
                    "enum": [str(item) for item in values],
                    "x-original-type": original,
                }
        if inferred_type is None:
            inferred_type = json_type
        elif inferred_type != json_type:
            return {
                "type": "string",
                "enum": [str(item) for item in values],
                "x-original-type": original,
            }
        normalized_values.append(value)

    schema: Dict[str, Any] = {"enum": normalized_values}
    if inferred_type == "null":
        schema["type"] = "null"
    else:
        schema["type"] = inferred_type or "string"

    if inferred_type is None or inferred_type == "null":
        schema.setdefault("x-original-type", original)

    return schema


def _normalize_type(type_name: str) -> Dict[str, Any]:
    """Normalize a type annotation string to JSON schema format."""
    if not type_name:
        return {}

    original = type_name.strip()
    if not original:
        return {}

    normalized = original.replace("typing.", "").strip()
    lower = normalized.lower()

    # Handle Literal types
    if lower.startswith("literal[") and normalized.endswith("]"):
        inner = normalized[len("Literal[") : -1]
        literal_schema = _normalize_literal_type(inner, original)
        if literal_schema:
            return literal_schema

    # Handle Optional types
    if lower.startswith("optional[") and normalized.endswith("]"):
        return _normalize_type(normalized[len("optional[") : -1])

    # Handle Union types
    if lower.startswith("union[") and normalized.endswith("]"):
        inner = normalized[len("union[") : -1]
        parts = [part.strip() for part in inner.split(",") if part.strip()]
        for part in parts:
            schema = _normalize_type(part)
            if schema:
                schema.setdefault("x-original-union", parts)
                return schema
        return {}

    # Handle pipe union types (str | int)
    if "|" in normalized:
        for part in (p.strip() for p in normalized.split("|") if p.strip()):
            schema = _normalize_type(part)
            if schema:
                return schema

    # Handle 'or' union types (str or int)
    if " or " in lower:
        for part in (p.strip() for p in normalized.split(" or ") if p.strip()):
            schema = _normalize_type(part)
            if schema:
                return schema

    # Handle array types
    array_prefixes = ("list", "sequence", "tuple", "set", "array")
    for prefix in array_prefixes:
        if lower.startswith(f"{prefix}[") and normalized.endswith("]"):
            inner = normalized[len(prefix) + 1 : -1]
            items_schema = _normalize_type(inner)
            schema: Dict[str, Any] = {"type": "array"}
            if items_schema:
                schema["items"] = items_schema
            elif inner.strip():
                schema["x-original-item-type"] = inner.strip()
            return schema
        if lower == prefix:
            return {"type": "array"}

    # Handle object/dict types
    if lower in {"dict", "mapping", "object"}:
        return {"type": "object"}

    # Handle simple types
    simple_map = {
        "int": "integer",
        "integer": "integer",
        "float": "number",
        "double": "number",
        "number": "number",
        "str": "string",
        "string": "string",
        "bool": "boolean",
        "boolean": "boolean",
        "datetime": "string",
        "date": "string",
        "time": "string",
        "any": "object",
    }
    if lower in simple_map:
        schema: Dict[str, Any] = {"type": simple_map[lower]}
        format_map = {"datetime": "date-time", "date": "date", "time": "time"}
        if lower in format_map:
            schema["format"] = format_map[lower]
        return schema

    # Handle generic types with parameters
    if "[" in normalized and normalized.endswith("]"):
        base, inner = normalized.split("[", 1)
        schema = _normalize_type(base)
        if schema.get("type") == "array" and "items" not in schema:
            inner_schema = _normalize_type(inner[:-1])
            if inner_schema:
                schema["items"] = inner_schema
        else:
            schema.setdefault("x-original-generic", normalized)
        return schema

    # Default fallback
    return {"type": "string", "x-original-type": original}
