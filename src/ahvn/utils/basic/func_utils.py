__all__ = [
    "code2func",
    "funcwrap",
    "parse_docstring",
    "synthesize_docstring",
    "synthesize_def",
    "synthesize_signature",
]

from docstring_parser import parse
from typing import Callable, Optional, Dict, Any, List
import inspect
import functools
import re

from .type_utils import (
    jsonschema_type,
    autotype,
)
from .str_utils import indent


_DEFAULT_SENTINEL = object()


def code2func(code: str, func_name: Optional[str] = None, env: Optional[Dict] = None):
    """\
    Extract a callable function from a code snippet.

    Warning:
        This function uses `exec()` to execute the provided code snippet.
        Executing arbitrary code is a security risk and can lead to remote code execution.
        Only use this function with trusted code sources. Do not use it to process
        untrusted user input.

    Args:
        code (str): The code snippet containing the function definition.
        func_name (Optional[str], optional): The name of the function to extract. Defaults to None.
            If None, and only one callable is found, that function will be used.
        env (Optional[Dict], optional): The environment in which to execute the code. Defaults to None.

    Returns:
        Callable: The extracted callable function.

    Raises:
        ValueError: If no callable is found or multiple callables without specifying func_name.
    """
    env = globals() | (env or dict())
    locals_dict = dict()
    exec(code, env, locals_dict)
    funcs = {k: v for k, v in locals_dict.items() if callable(v)}
    if not funcs:
        raise ValueError("No callable found in the provided code.")
    if (func_name is None) and (len(funcs) > 1):
        raise ValueError("Multiple callables found in the provided code. Please provide a single function or specify the function name via `func_name`.")
    if (func_name is None) and (len(funcs) == 1):
        func_name = funcs[next(iter(funcs))].__name__
    if (func_name not in funcs) or (not callable(funcs[func_name])):
        raise ValueError(f"No callable named '{func_name}' found in the provided code.")
    return funcs[func_name]


def _coerce_doc_default(value: Optional[str], schema_type: Optional[str]) -> Any:
    """Coerce a default value from docstring to the appropriate type."""
    if value is None:
        return _DEFAULT_SENTINEL
    raw = value.strip()
    if not raw:
        return _DEFAULT_SENTINEL

    # Use autotype for intelligent conversion
    try:
        converted = autotype(raw)
        # For target types, ensure the converted value matches expectations
        if schema_type == "integer" and isinstance(converted, (int, float)):
            return int(converted)
        elif schema_type == "number" and isinstance(converted, (int, float)):
            return float(converted)
        elif schema_type == "boolean" and isinstance(converted, bool):
            return converted
        return converted
    except Exception:
        return raw


def _coerce_signature_default(value: Any) -> Any:
    """Coerce a default value from function signature."""
    if value is inspect._empty:
        return _DEFAULT_SENTINEL
    if isinstance(value, (int, float, bool, str)) or value is None:
        return value
    return _DEFAULT_SENTINEL


def _clean_text(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    stripped = text.strip()
    return stripped or None


def _compose_description(parsed) -> Optional[str]:
    parts = [_clean_text(parsed.short_description), _clean_text(parsed.long_description)]
    parts = [part for part in parts if part]
    if not parts:
        return None
    return "\n\n".join(parts)


def _extract_section_lines(docstring: str, section_name: str) -> List[str]:
    lines = docstring.splitlines()
    collected: List[str] = []
    in_section = False
    section_lower = f"{section_name.lower()}:"

    for raw_line in lines:
        stripped = raw_line.strip()
        if not in_section:
            if stripped.lower() == section_lower:
                in_section = True
            continue

        if stripped.endswith(":") and not raw_line.startswith((" ", "\t")):
            break

        collected.append(stripped)

    while collected and not collected[0]:
        collected.pop(0)
    while collected and not collected[-1]:
        collected.pop()
    return collected


def _summarize_docstring_args(parsed, signature) -> Optional[Dict[str, Any]]:
    if not parsed.params:
        return None

    signature_params = signature.parameters if signature else {}
    properties: Dict[str, Dict[str, Any]] = {}
    required: List[str] = []
    for param in parsed.params:
        schema_entry = jsonschema_type(param.type_name)
        if "type" not in schema_entry:
            schema_entry["type"] = "string"
            if param.type_name:
                schema_entry.setdefault("x-original-type", param.type_name)

        description = _clean_text(param.description)
        if description:
            schema_entry["description"] = description

        doc_default = _coerce_doc_default(param.default, schema_entry.get("type"))

        signature_default = _DEFAULT_SENTINEL
        signature_has_default = False
        if signature_params:
            signature_param = signature_params.get(param.arg_name)
            if signature_param is not None:
                signature_has_default = signature_param.default is not inspect._empty
                signature_default = _coerce_signature_default(signature_param.default)

        effective_default = doc_default
        if effective_default is _DEFAULT_SENTINEL and signature_default is not _DEFAULT_SENTINEL:
            effective_default = signature_default

        if effective_default is not _DEFAULT_SENTINEL:
            schema_entry["default"] = effective_default

        properties[param.arg_name] = schema_entry

        is_optional = bool(param.is_optional)
        if not is_optional and signature_has_default:
            is_optional = True
        if not is_optional and effective_default is not _DEFAULT_SENTINEL:
            is_optional = True

        if not is_optional:
            required.append(param.arg_name)

    args_schema: Dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        args_schema["required"] = required

    return args_schema


def _build_return_entry(type_name: Optional[str], description: Optional[str], is_generator: bool, name: Optional[str]) -> Dict[str, Any]:
    schema = jsonschema_type(type_name)
    if not schema:
        schema = {"type": "string"}
    elif "type" not in schema:
        schema["type"] = "string"
        if type_name:
            schema.setdefault("x-original-type", type_name)

    entry: Dict[str, Any] = {"schema": schema}

    clean_description = _clean_text(description)
    if clean_description:
        entry["description"] = clean_description

    clean_name = _clean_text(name)
    if clean_name:
        entry["name"] = clean_name

    if is_generator:
        entry["is_generator"] = True

    return entry


def _parse_structured_return_description(description: Optional[str]) -> Optional[Dict[str, Dict[str, Any]]]:
    """\
    Parse structured return description to extract field definitions.

    Expects format like:
        A dictionary containing:
            - field_name (type): description
            - another_field (type): description

    Or:
        field_name (type): description
        another_field (type): description

    Returns:
        Dict mapping field names to their schema definitions, or None if not parseable.
    """
    if not description:
        return None

    lines = description.strip().split("\n")
    properties: Dict[str, Dict[str, Any]] = {}

    for line in lines:
        line = line.strip()
        if not line or line.endswith(":"):
            continue

        # Remove leading dash/bullet
        if line.startswith(("-", "*", "•")):
            line = line[1:].strip()

        # Try to match pattern: field_name (type): description
        match = re.match(r"^(\w+)\s*\(([^)]+)\)\s*:\s*(.*)$", line)
        if match:
            field_name, type_str, field_desc = match.groups()
            field_schema = jsonschema_type(type_str.strip())
            if not field_schema:
                field_schema = {"type": "string"}
            if field_desc.strip():
                field_schema["description"] = field_desc.strip()
            properties[field_name] = field_schema

    return properties if properties else None


def _build_returns(parsed) -> Optional[Dict[str, Any]]:
    """\
    Build an output schema from the parsed return information.

    MCP spec requires output schemas to be of type "object". This function:
    1. For simple types: wraps in {"result": <type>}
    2. For dict/object with structured description: parses fields into properties
    3. For named returns: uses the name as the property key
    """
    if not parsed.returns:
        return None

    return_type = parsed.returns.type_name
    return_desc = parsed.returns.description
    return_name = parsed.returns.return_name

    # Normalize the return type
    type_schema = jsonschema_type(return_type)
    if not type_schema:
        type_schema = {"type": "string"}
    elif "type" not in type_schema:
        type_schema["type"] = "string"
        if return_type:
            type_schema.setdefault("x-original-type", return_type)

    # Try to parse structured fields from description for object/dict/array types
    if type_schema.get("type") in ("object", "dict", "array"):
        structured_fields = _parse_structured_return_description(return_desc)
        if structured_fields:
            # Build object schema with parsed properties
            output_schema = {"type": "object", "properties": structured_fields}
            if return_desc:
                output_schema["description"] = _clean_text(return_desc)
            return output_schema

    # Determine the property name for the return value
    property_name = _clean_text(return_name) or "result"

    # Add description if available
    if return_desc:
        type_schema["description"] = _clean_text(return_desc)

    # Wrap in object schema as required by MCP spec
    output_schema = {"type": "object", "properties": {property_name: type_schema}}

    return output_schema


def _split_many_returns(parsed, has_primary: bool) -> Dict[str, List[Dict[str, Any]]]:
    entries = getattr(parsed, "many_returns", None)
    if not entries:
        return {}

    yields_meta: List[Dict[str, Any]] = []
    additional_returns: List[Dict[str, Any]] = []

    for item in entries:
        entry = _build_return_entry(
            item.type_name,
            item.description,
            item.is_generator,
            item.return_name,
        )
        if item.is_generator:
            yields_meta.append(entry)
        else:
            additional_returns.append(entry)

    result: Dict[str, List[Dict[str, Any]]] = {}
    if yields_meta:
        result["yields"] = yields_meta
    if additional_returns and (not has_primary or len(additional_returns) > 1):
        result["returns_list"] = additional_returns
    return result


def _build_raises(parsed) -> Optional[List[Dict[str, Any]]]:
    if not parsed.raises:
        return None
    return [
        {
            "type": raise_.type_name,
            "description": _clean_text(raise_.description),
        }
        for raise_ in parsed.raises
    ]


def _build_examples(parsed, docstring: str) -> Optional[List[Dict[str, Any]]]:
    if not parsed.examples:
        return None

    examples_meta = [
        {
            "description": _clean_text(example.description),
            "snippet": example.snippet,
        }
        for example in parsed.examples
    ]

    if not any(entry["description"] or entry["snippet"] for entry in examples_meta):
        fallback_lines = _extract_section_lines(docstring, "Examples")
        if fallback_lines:
            examples_meta = [
                {
                    "description": "\n".join(fallback_lines),
                    "snippet": None,
                }
            ]

    return examples_meta


def _build_deprecation(parsed) -> Optional[Dict[str, Any]]:
    if not parsed.deprecation:
        return None
    description = _clean_text(getattr(parsed.deprecation, "description", None))
    version = _clean_text(getattr(parsed.deprecation, "versions", None)) or _clean_text(getattr(parsed.deprecation, "version", None))
    return {"description": description, "version": version}


def parse_docstring(func: Callable) -> Dict[str, Any]:
    """\
    Parse the docstring of a Python function.

    Args:
        func (Callable): The Python function whose docstring is to be parsed.

    Returns:
        Dict: A dictionary containing the parsed components of the docstring.
    """
    docstring = inspect.getdoc(func)
    if not docstring:
        return {}

    parsed = parse(docstring)

    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        signature = None

    result: Dict[str, Any] = {}

    description = _compose_description(parsed)
    if description:
        result["description"] = description

    args_summary = _summarize_docstring_args(parsed, signature)
    if args_summary:
        result["args"] = args_summary

    returns_meta = _build_returns(parsed)
    if returns_meta:
        result["returns"] = returns_meta

    split_returns = _split_many_returns(parsed, has_primary=bool(returns_meta))
    result.update(split_returns)

    raises_meta = _build_raises(parsed)
    if raises_meta:
        result["raises"] = raises_meta

    examples_meta = _build_examples(parsed, docstring)
    if examples_meta:
        result["examples"] = examples_meta

    deprecation_meta = _build_deprecation(parsed)
    if deprecation_meta:
        result["deprecation"] = deprecation_meta

    if parsed.style:
        result["style"] = parsed.style.name

    return result


def _jsonschema_type_to_python(schema: Dict[str, Any]) -> str:
    """\
    Convert JSON schema type to Python type hint string.

    Args:
        schema (Dict[str, Any]): JSON schema definition.

    Returns:
        str: Python type hint string.
    """
    schema_type = schema.get("type")

    # Check for x-original-type first
    if "x-original-type" in schema:
        return schema["x-original-type"]

    # Handle array type
    if schema_type == "array":
        items = schema.get("items", {})
        item_type = _jsonschema_type_to_python(items) if items else "Any"
        return f"List[{item_type}]"

    # Handle object/dict type
    if schema_type in ("object", "dict"):
        return "Dict[str, Any]"

    # Handle basic types
    type_map = {
        "string": "str",
        "integer": "int",
        "number": "float",
        "boolean": "bool",
        "null": "None",
    }

    return type_map.get(schema_type, "Any")


def _format_param_description(param_name: str, schema: Dict[str, Any], required: bool) -> str:
    """\
    Format a parameter description for docstring.

    Args:
        param_name (str): Name of the parameter.
        schema (Dict[str, Any]): JSON schema for the parameter.
        required (bool): Whether the parameter is required.

    Returns:
        str: Formatted parameter description line.
    """
    type_hint = _jsonschema_type_to_python(schema)
    description = schema.get("description", "")
    default = schema.get("default")

    # Build the description line
    parts = [f"{param_name} ({type_hint})"]

    # Add description
    if description:
        parts.append(f": {description}")
    else:
        parts.append(":")

    # Add default/optional info
    if not required and default is not None:
        parts.append(f" Defaults to {repr(default)}.")
    elif not required:
        parts.append(" Optional.")

    return "".join(parts)


def _format_return_description(output_schema: Dict[str, Any]) -> str:
    """\
    Format return value description for docstring.

    Args:
        output_schema (Dict[str, Any]): Output schema from tool.

    Returns:
        str: Formatted return description.
    """
    if (output_schema or {}).get("type") != "object":
        return "Any: The return value"

    properties = (output_schema or {}).get("properties", {})

    # Single property case - unwrap it
    if len(properties) == 1:
        prop_name, prop_schema = next(iter(properties.items()))
        type_hint = _jsonschema_type_to_python(prop_schema)
        description = prop_schema.get("description", "The return value")
        return f"{type_hint}: {description}"

    # Multiple properties - format as dict with fields
    if len(properties) > 1:
        first_line = "Dict[str, Any]: A dictionary containing:"
        property_lines = []
        for prop_name, prop_schema in properties.items():
            type_hint = _jsonschema_type_to_python(prop_schema)
            description = prop_schema.get("description", "")
            if description:
                property_lines.append(f"- {prop_name} ({type_hint}): {description}")
            else:
                property_lines.append(f"- {prop_name} ({type_hint})")

        indented_properties = indent("\n".join(property_lines), tab=4)
        return f"{first_line}\n{indented_properties}"

    return "Any: The return value"


def synthesize_docstring(
    description: Optional[str] = None,
    input_schema: Optional[Dict[str, Any]] = None,
    output_schema: Optional[Dict[str, Any]] = None,
    style: str = "google",
) -> str:
    """\
    Synthesize a docstring from tool specification attributes.

    Args:
        description (Optional[str], optional): Tool description. Defaults to None.
        input_schema (Optional[Dict[str, Any]], optional): Parameters schema (JSON schema object). Defaults to None.
        output_schema (Optional[Dict[str, Any]], optional): Output schema (JSON schema object). Defaults to None.
        style (str, optional): Docstring style ('google', 'numpy', 'rest'). Defaults to 'google'.

    Returns:
        str: The synthesized docstring.
    """
    if style != "google":
        raise NotImplementedError(f"Docstring style '{style}' is not yet supported. Only 'google' style is currently implemented.")

    lines = []

    # Add description
    if description:
        # Handle multi-line descriptions
        desc_lines = description.strip().split("\n")
        lines.extend(desc_lines)
        lines.append("")

    # Add Args section
    properties = (input_schema or {}).get("properties", {})
    if properties:
        lines.append("Args:")
        required_params = set((input_schema or {}).get("required", []))

        param_lines = []
        for param_name, param_schema in properties.items():
            is_required = param_name in required_params
            param_desc = _format_param_description(param_name, param_schema, is_required)
            param_lines.append(param_desc)

        if param_lines:
            indented_params = indent("\n".join(param_lines), tab=4)
            lines.append(indented_params)

        lines.append("")

    # Add Returns section
    if output_schema:
        lines.append("Returns:")
        return_desc = _format_return_description(output_schema)
        indented_return = indent(return_desc, tab=4)
        lines.append(indented_return)

    # Join all lines and ensure proper formatting
    docstring = "\n".join(lines)

    # Remove trailing empty line if present
    docstring = docstring.rstrip("\n")

    return docstring


def synthesize_def(
    name: str,
    input_schema: Optional[Dict[str, Any]] = None,
    output_schema: Optional[Dict[str, Any]] = None,
    docstring: Optional[str] = None,
    code: str = "pass",
) -> str:
    """Generate a Python function definition from schema metadata."""
    param_list: List[str] = []
    properties = (input_schema or {}).get("properties", {})
    for param_name, param_schema in properties.items():
        type_hint = _jsonschema_type_to_python(param_schema)
        param_str = f"{param_name}: {type_hint}"

        if "default" in param_schema:
            param_str += f" = {repr(param_schema['default'])}"

        param_list.append(param_str)

    return_annotation = "Any"
    if (output_schema or {}).get("type") == "object":
        properties = (output_schema or {}).get("properties", {})
        if len(properties) == 1:
            prop_schema = next(iter(properties.values()))
            return_annotation = _jsonschema_type_to_python(prop_schema)
        elif properties:
            return_annotation = "Dict[str, Any]"
    elif output_schema:
        return_annotation = _jsonschema_type_to_python(output_schema)

    params_str = ", ".join(param_list)
    lines = [f"def {name}({params_str}) -> {return_annotation}:"]

    if docstring:
        full_docstring = f'"""\\\n{docstring}\n"""'
        indented_docstring_block = indent(full_docstring, tab=4)
        lines.append(indented_docstring_block)

    indented_code = indent(code, tab=4)
    lines.append(indented_code)
    return "\n".join(lines)


def synthesize_signature(
    name: str,
    input_schema: Optional[Dict[str, Any]] = None,
    arguments: Optional[Dict[str, Any]] = None,
) -> str:
    """Generate a Python function call signature with provided arguments and default values.

    Args:
        name: The function name.
        input_schema: JSON schema for function input_schema (same format as synthesize_def).
        arguments: Dict of argument values to include in the signature. Missing arguments
                  will use their default values from the schema.

    Returns:
        str: The function call signature, e.g., "f(a=1, b=5)".

    Example:
        >>> synthesize_signature("f", {"type": "object", "properties": {"a": {"type": "int"}, "b": {"type": "int", "default": 5}}}, {"a": 1})
        'f(a=1, b=5)'
    """
    properties = (input_schema or {}).get("properties", {})
    arguments = arguments or {}
    required_params = set((input_schema or {}).get("required", []))

    arg_list: List[str] = []
    for param_name, param_schema in properties.items():
        if param_name in arguments:
            arg_list.append(f"{param_name}={repr(arguments[param_name])}")
        elif "default" in param_schema:
            arg_list.append(f"{param_name}={repr(param_schema['default'])}")
        elif param_name in required_params:
            arg_list.append(param_name)
        else:
            raise ValueError(f"Missing value for optional parameter '{param_name}' with no default.")

    args_str = ", ".join(arg_list)
    return f"{name}({args_str})"


def funcwrap(exec_func: Callable, sig_func: Callable) -> Callable:
    """\
    Create a wrapper function that calls `exec_func` but has the signature and metadata of `sig_func`.

    Args:
        exec_func: The function to be called (the implementation).
        sig_func: The function whose signature and metadata should be adopted.

    Returns:
        Callable: A wrapper function.
    """
    sig = inspect.signature(sig_func)

    @functools.wraps(sig_func)
    def wrapper(*args, **kwargs):
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        return exec_func(**bound.arguments)

    return wrapper
