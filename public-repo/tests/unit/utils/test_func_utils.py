from ahvn.utils.basic.func_utils import parse_docstring
from typing import Literal


def magic_add(a: int, b: int = 5, c: Literal[42, 0] = 42) -> int:
    """\
    Input two numbers a and b, return a + b + c.

    Note: This is a sample function to demonstrate docstring parsing.
        c is a literal that can only be 42 or 0.

    Args:
        a (int): The first number to add.
        b (int, optional): The second number to add. Defaults to 5.
        c (Literal[42, 0], optional): A literal that can only be 42 or 0. Defaults to 42.

    Returns:
        int: The result a + b + c.

    Yields:
        None

    Raises:
        ValueError: If a or b is not an integer.

    Examples:
        >>> magic_add(3)
        50
        >>> magic_add(a=7, b=1)
        50
    """
    return a + b + c


def _rich_function(a: int, b: int = 5, payload=None, name: str | None = None) -> int:
    """Compute something useful.

    Args:
        a (int): Primary value.
        b (int, optional): Secondary value. Defaults to 5.
        payload (CustomType): Extra input.
        name: Optional label.

    Returns:
        int: Cool result.

    Raises:
        ValueError: When everything fails.
    """

    return a + (b or 0)


def _complex_types(items, flag: bool = False, count=None):
    """Showcase complex type parsing.

    Args:
        items (List[str]): Values to process.
        flag (bool): Toggle additional behavior.
        count (Optional[int], optional): Limit of items. Defaults to None.

    Returns:
        list[str]: Processed values.
    """

    return []


def _no_docstring_function():
    return None


def _multi_returns_function(flag: bool, mode: Literal["fast", "safe"] = "fast") -> tuple[str, int]:
    """Process data and demonstrate multiple returns.

    Args:
        flag (bool): Toggle extended behavior.
        mode (Literal["fast", "safe"], optional): Execution strategy. Defaults to "fast".

    Returns:
        tuple[str, int]: Primary summary of processing.
        dict[str, Any]: Additional metadata captured during execution.
        list[str]: Ordered step identifiers.

    Yields:
        Literal["step", "done"]: Streaming status updates.

    Raises:
        RuntimeError: If processing fails.
    """

    return ("ok", 1)


class TestParseDocstring:
    """Test suite for parse_docstring utility."""

    def test_generates_openai_schema(self):
        """Validate JSON schema generation for arguments."""
        result = parse_docstring(_rich_function)
        assert result["description"] == "Compute something useful."

        args_schema = result["args"]
        properties = args_schema["properties"]

        assert args_schema["type"] == "object"
        assert args_schema["required"] == ["a"]

        assert properties["a"]["type"] == "integer"
        assert "default" not in properties["a"]

        assert properties["b"]["type"] == "integer"
        assert properties["b"]["default"] == 5

        assert properties["payload"]["type"] == "string"
        assert properties["payload"]["default"] is None
        assert properties["payload"]["x-original-type"] == "CustomType"

        assert properties["name"]["type"] == "string"
        assert properties["name"]["default"] is None

        returns_meta = result["returns"]
        # MCP spec requires object output schemas, simple types are wrapped
        assert returns_meta["type"] == "object"
        assert "result" in returns_meta["properties"]
        assert returns_meta["properties"]["result"]["type"] == "integer"
        assert returns_meta["properties"]["result"]["description"] == "Cool result."
        assert result["raises"][0]["type"] == "ValueError"
        assert result["style"] == "GOOGLE"
        assert "meta" not in result

    def test_complex_types_and_optionals(self):
        """Ensure complex docstring types are handled safely."""
        result = parse_docstring(_complex_types)
        args_schema = result["args"]
        properties = args_schema["properties"]

        assert properties["items"]["type"] == "array"
        assert properties["items"]["items"]["type"] == "string"
        assert properties["flag"]["type"] == "boolean"
        assert properties["flag"]["default"] is False
        assert properties["count"]["type"] == "integer"
        assert properties["count"]["default"] is None
        assert args_schema["required"] == ["items"]

    def test_missing_docstring_returns_empty(self):
        """Functions without docstring should yield empty metadata."""
        result = parse_docstring(_no_docstring_function)
        assert result == {}

    def test_magic_add_regression(self):
        """Regression test mirroring temp.py magic_add behavior."""
        result = parse_docstring(magic_add)
        description = "Input two numbers a and b, return a + b + c.\n\nNote: This is a sample function to demonstrate docstring parsing.\n    c is a literal that can only be 42 or 0."
        assert result["description"] == description

        props = result["args"]["properties"]

        assert result["args"]["required"] == ["a"]
        assert props["a"]["type"] == "integer"
        assert "default" not in props["a"]

        assert props["b"]["type"] == "integer"
        assert props["b"]["default"] == 5
        assert props["c"]["type"] == "integer"
        assert props["c"]["enum"] == [42, 0]
        assert props["c"]["default"] == 42

        # MCP spec requires object output schemas
        assert result["returns"]["type"] == "object"
        assert "result" in result["returns"]["properties"]
        assert result["returns"]["properties"]["result"]["type"] == "integer"
        assert result["yields"][0]["description"] == "None"
        assert result["yields"][0]["schema"]["type"] == "string"
        assert result["examples"][0]["description"].startswith(">>> magic_add(3)")

    def test_multiple_returns_and_yields(self):
        """Ensure multiple returns and yields flatten correctly."""

        result = parse_docstring(_multi_returns_function)

        assert result["description"] == "Process data and demonstrate multiple returns."

        args_schema = result["args"]
        assert args_schema["required"] == ["flag"]
        props = args_schema["properties"]
        assert props["mode"]["enum"] == ["fast", "safe"]
        assert props["mode"]["default"] == "fast"

        primary_return = result["returns"]
        # MCP spec requires object output schemas, arrays are wrapped
        assert primary_return["type"] == "object"
        assert "result" in primary_return["properties"]
        assert primary_return["properties"]["result"]["type"] == "array"
        assert "Additional metadata" in primary_return["properties"]["result"]["description"]
        assert "returns_list" not in result

        yields_meta = result["yields"]
        assert yields_meta[0]["schema"]["enum"] == ["step", "done"]

        raises_meta = result["raises"]
        assert raises_meta[0]["type"] == "RuntimeError"

        assert result["style"] == "GOOGLE"
