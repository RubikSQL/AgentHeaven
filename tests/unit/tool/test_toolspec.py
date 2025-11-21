import textwrap
import sys
import os

import pytest

from ahvn.tool.base import ToolSpec
from fastmcp.tools import Tool as FastMCPTool
from mcp.types import Tool as MCPTool


def fibonacci(n: int) -> int:
    """Compute the nth Fibonacci number using an efficient iterative approach.

    The Fibonacci sequence is defined as:
    - F(0) = 0
    - F(1) = 1
    - F(n) = F(n-1) + F(n-2) for n > 1

    This implementation runs in O(n) time and O(1) space complexity.

    Args:
        n (int): The position in the Fibonacci sequence to compute. Must be a non-negative integer.
            For practical purposes, n should be less than 1000 to avoid extremely large numbers.

    Returns:
        int: The nth Fibonacci number.

    Raises:
        ValueError: If n is negative.
        OverflowError: If the result is too large to fit in standard integer representation.

    Examples:
        >>> fibonacci(0)
        0
        >>> fibonacci(1)
        1
        >>> fibonacci(10)
        55
        >>> fibonacci(20)
        6765
    """
    if n < 0:
        raise ValueError("n must be a non-negative integer")
    elif n == 0:
        return 0
    elif n == 1:
        return 1

    # Use iterative approach for better performance
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b

    return b


def sample_tool(left: int, right: int = 10) -> int:
    """Add two numbers.

    Args:
        left (int): Left operand.
        right (int): Right operand. Defaults to 10.

    Returns:
        int: Sum of the operands.
    """
    return left + right


FUNCTION_CODE = textwrap.dedent(
    '''
    def sample_tool(left: int, right: int = 10) -> int:
        """Add two numbers.

        Args:
            left (int): Left operand.
            right (int): Right operand. Defaults to 10.

        Returns:
            int: Sum of the operands.
        """
        return left + right
    '''
)


@pytest.mark.parametrize("source", ["function", "code", "mcp"], ids=["from_function", "from_code", "from_mcp"])
@pytest.mark.parametrize(
    "destination",
    ["jsonschema", "mcp", "docstring", "code", "prompt"],
)
def test_toolspec_conversions(source: str, destination: str):
    if source == "function":
        spec = ToolSpec.from_function(sample_tool)
    elif source == "code":
        spec = ToolSpec.from_code(FUNCTION_CODE, func_name="sample_tool")
    elif source == "mcp":
        spec = ToolSpec.from_mcp(FastMCPTool.from_function(sample_tool))
    else:
        raise ValueError(f"Unsupported source: {source}")

    if destination == "jsonschema":
        schema = spec.to_jsonschema()
        assert schema["name"] == "sample_tool"
        assert schema["parameters"]["properties"]["left"]["type"] == "integer"
        assert schema["parameters"]["properties"]["right"]["default"] == 10
        assert schema["strict"] is True
    elif destination == "mcp":
        mcp_tool = spec.to_mcp()
        assert isinstance(mcp_tool, MCPTool)
        assert mcp_tool.name == "sample_tool"
        assert mcp_tool.inputSchema["properties"]["right"]["default"] == 10
    elif destination == "docstring":
        docstring = spec.docstring
        assert isinstance(docstring, str)
        assert "Add two numbers" in docstring
        assert "left" in docstring and "right" in docstring
    elif destination == "code":
        code_text = spec.code
        assert "def sample_tool(" in code_text
        assert '"""' in code_text
        assert "pass" in code_text
    elif destination == "prompt":
        prompt = spec.to_prompt()
        assert "- `sample_tool(left, right=10)`" in prompt
        lines = prompt.splitlines()
        if len(lines) > 1:
            assert lines[1].startswith("    ")
            assert "Add two numbers" in prompt
    else:
        raise ValueError(f"Unsupported destination: {destination}")


def test_toolspec_bound_method_signature():
    class Adder:
        def __init__(self, bias: int) -> None:
            self._bias = bias

        def shift(self, value: int) -> int:
            """Shift the value by bias."""
            return value + self._bias

    spec = ToolSpec.from_function(Adder(5).shift)
    fast_tool = spec.to_fastmcp()
    assert "value" in fast_tool.parameters["properties"]
    assert "self" not in fast_tool.parameters["properties"]


def test_examples_reference_is_preserved_and_mutable():
    examples: list[dict[str, int]] = []
    spec = ToolSpec.from_function(sample_tool, examples=examples)

    assert spec.examples is examples

    examples.append({"left": 7, "right": 3})
    assert spec.examples is examples
    assert spec.examples[0]["left"] == 7


# Fibonacci ToolSpec Tests
class TestFibonacciToolSpec:
    """Comprehensive tests for the fibonacci ToolSpec implementation."""

    def test_fibonacci_toolspec_creation(self):
        """Test creating ToolSpec from fibonacci function."""
        examples = [
            {"inputs": {"n": 0}, "expected": 0},
            {"inputs": {"n": 1}, "expected": 1},
            {"inputs": {"n": 5}, "expected": 5},
            {"inputs": {"n": 10}, "expected": 55},
        ]

        fib_spec = ToolSpec.from_function(func=fibonacci, examples=examples, parse_docstring=True)

        assert fib_spec.tool.name == "fibonacci"
        assert "Compute the nth Fibonacci number" in fib_spec.tool.description
        assert fib_spec.examples == examples

    def test_fibonacci_signature(self):
        """Test fibonacci function signature generation."""
        fib_spec = ToolSpec.from_function(fibonacci)

        # Test default signature
        default_sig = fib_spec.signature()
        assert default_sig == "fibonacci(n)"

        # Test signature with arguments (note: signature includes parameter names)
        arg_sig = fib_spec.signature(n=10)
        assert arg_sig == "fibonacci(n=10)"

        # Test signature with multiple arguments (though fibonacci only takes one)
        complex_sig = fib_spec.signature(n=63)
        assert complex_sig == "fibonacci(n=63)"

    def test_fibonacci_code_generation(self):
        """Test fibonacci function code generation."""
        fib_spec = ToolSpec.from_function(fibonacci)

        code = fib_spec.code
        assert "def fibonacci(" in code
        assert "n: int" in code
        assert "-> int:" in code
        assert '"""' in code
        assert "Compute the nth Fibonacci number" in code
        assert "pass" in code  # Generated code should have pass placeholder

    def test_fibonacci_docstring_extraction(self):
        """Test docstring extraction from fibonacci function."""
        fib_spec = ToolSpec.from_function(fibonacci, parse_docstring=True)

        docstring = fib_spec.docstring
        assert "Compute the nth Fibonacci number" in docstring
        assert "F(0) = 0" in docstring
        assert "F(1) = 1" in docstring
        assert "O(n) time and O(1) space" in docstring
        assert "Args:" in docstring
        assert "Returns:" in docstring
        assert "Raises:" not in docstring  # It should be excluded as it is not standard in tool
        # assert "Examples:" in docstring  # Examples are not implemented for now

    def test_fibonacci_json_schema(self):
        """Test JSON schema generation for fibonacci function."""
        fib_spec = ToolSpec.from_function(fibonacci)

        schema = fib_spec.to_jsonschema()

        # Test basic schema structure
        assert schema["name"] == "fibonacci"
        assert schema["strict"] is True
        assert "parameters" in schema
        assert schema["parameters"]["type"] == "object"

        # Test parameter definition
        properties = schema["parameters"]["properties"]
        assert "n" in properties
        assert properties["n"]["type"] == "integer"
        # Description is extracted from the docstring when parse_docstring=True
        description = properties["n"]["description"]
        assert "position in the Fibonacci sequence" in description
        assert "non-negative integer" in description

        # Test required parameters
        assert "n" in schema["parameters"]["required"]

    def test_fibonacci_mcp_conversion(self):
        """Test conversion to MCP tool format."""
        fib_spec = ToolSpec.from_function(fibonacci)

        mcp_tool = fib_spec.to_mcp()

        assert mcp_tool.name == "fibonacci"
        assert "Compute the nth Fibonacci number" in mcp_tool.description
        assert "properties" in mcp_tool.inputSchema
        assert "n" in mcp_tool.inputSchema["properties"]

    def test_fibonacci_prompt_generation(self):
        """Test prompt representation generation."""
        fib_spec = ToolSpec.from_function(fibonacci)

        prompt = fib_spec.to_prompt()
        assert "- `fibonacci(n)`" in prompt
        lines = prompt.splitlines()

        if len(lines) > 1:
            assert lines[1].startswith("    ")
            assert "Compute the nth Fibonacci number" in prompt

    def test_fibonacci_function_calling(self):
        """Test direct function calling through ToolSpec."""
        fib_spec = ToolSpec.from_function(fibonacci)

        # Test basic fibonacci values
        assert fib_spec.call(n=0) == 0
        assert fib_spec.call(n=1) == 1
        assert fib_spec.call(n=5) == 5
        assert fib_spec.call(n=10) == 55
        assert fib_spec.call(n=15) == 610

        # Test the specific case from the example
        result_63 = fib_spec.call(n=63)
        assert isinstance(result_63, int)
        assert result_63 > 0  # fibonacci(63) should be positive

    def test_fibonacci_error_handling(self):
        """Test error handling in fibonacci function calls."""
        fib_spec = ToolSpec.from_function(fibonacci)

        # Test negative input
        with pytest.raises(ValueError, match="n must be a non-negative integer"):
            fib_spec.call(n=-1)

    def test_fibonacci_from_code(self):
        """Test creating ToolSpec from fibonacci code string."""
        fib_code = '''
def fibonacci(n: int) -> int:
    """Compute the nth Fibonacci number."""
    if n < 0:
        raise ValueError("n must be non-negative")
    elif n <= 1:
        return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b
'''.strip()

        fib_spec = ToolSpec.from_code(fib_code, func_name="fibonacci")

        assert fib_spec.tool.name == "fibonacci"
        assert fib_spec.call(n=10) == 55

    def test_fibonacci_from_mcp(self):
        """Test creating ToolSpec from MCP tool."""
        fastmcp_tool = FastMCPTool.from_function(fibonacci)
        fib_spec = ToolSpec.from_mcp(fastmcp_tool)

        assert fib_spec.tool.name == "fibonacci"
        assert fib_spec.call(n=10) == 55

    def test_fibonacci_all_conversions(self):
        """Test all conversion methods for fibonacci function."""
        examples = [
            {"inputs": {"n": 0}, "expected": 0},
            {"inputs": {"n": 1}, "expected": 1},
            {"inputs": {"n": 10}, "expected": 55},
        ]

        # Create spec with examples
        fib_spec = ToolSpec.from_function(fibonacci, examples=examples)

        # Test all conversion methods
        json_schema = fib_spec.to_jsonschema()
        assert json_schema["name"] == "fibonacci"

        mcp_tool = fib_spec.to_mcp()
        assert mcp_tool.name == "fibonacci"

        docstring = fib_spec.docstring
        assert isinstance(docstring, str)
        assert "Fibonacci" in docstring

        code = fib_spec.code
        assert "def fibonacci(" in code

        prompt = fib_spec.to_prompt()
        assert "fibonacci" in prompt

        # Test examples are preserved
        assert fib_spec.examples == examples

    def test_fibonacci_large_number(self):
        """Test fibonacci with reasonably large numbers."""
        fib_spec = ToolSpec.from_function(fibonacci)

        # Test fibonacci(20) = 6765
        result = fib_spec.call(n=20)
        assert result == 6765

        # Test fibonacci(30) = 832040
        result = fib_spec.call(n=30)
        assert result == 832040

    @pytest.mark.parametrize("source", ["function", "code", "mcp"], ids=["from_function", "from_code", "from_mcp"])
    def test_fibonacci_parametrized_conversions(self, source: str):
        """Parametrized test for fibonacci conversion methods."""
        if source == "function":
            spec = ToolSpec.from_function(fibonacci)
        elif source == "code":
            fib_code = '''
def fibonacci(n: int) -> int:
    """Compute nth fibonacci."""
    return 0 if n <= 0 else 1 if n == 1 else fibonacci(n-1) + fibonacci(n-2)
'''.strip()
            spec = ToolSpec.from_code(fib_code, func_name="fibonacci")
        elif source == "mcp":
            spec = ToolSpec.from_mcp(FastMCPTool.from_function(fibonacci))

        # Test that all conversion methods work
        json_schema = spec.to_jsonschema()
        assert json_schema["name"] == "fibonacci"

        mcp_tool = spec.to_mcp()
        assert mcp_tool.name == "fibonacci"

        prompt = spec.to_prompt()
        assert "fibonacci" in prompt
