import pytest
from ahvn.utils.basic.type_utils import (
    jsonschema_type,
    parse_function_signature,
    autotype,
)
import inspect
from typing import Optional, List, Dict


class TestInferJsonSchema:
    """Test suite for jsonschema_type function."""

    def test_simple_types(self):
        """Test normalization of simple types."""
        assert jsonschema_type("int") == {"type": "integer"}
        assert jsonschema_type("str") == {"type": "string"}
        assert jsonschema_type("bool") == {"type": "boolean"}
        assert jsonschema_type("float") == {"type": "number"}

    def test_generic_array_types(self):
        """Test normalization of generic array types."""
        schema = jsonschema_type("List[str]")
        assert schema["type"] == "array"
        assert schema["items"]["type"] == "string"

        schema = jsonschema_type("list[int]")
        assert schema["type"] == "array"
        assert schema["items"]["type"] == "integer"

    def test_optional_types(self):
        """Test normalization of optional types."""
        schema = jsonschema_type("Optional[str]")
        assert schema["type"] == "string"

    def test_union_types(self):
        """Test normalization of union types."""
        schema = jsonschema_type("Union[str, int]")
        # Should take the first valid type
        assert schema["type"] == "string"
        assert "x-original-union" in schema

    def test_pipe_union_types(self):
        """Test normalization of pipe union types."""
        schema = jsonschema_type("str | int")
        assert schema["type"] == "string"

    def test_literal_types(self):
        """Test normalization of literal types."""
        schema = jsonschema_type("Literal['fast', 'slow']")
        assert schema["type"] == "string"
        assert set(schema["enum"]) == {"fast", "slow"}

    def test_datetime_formats(self):
        """Test datetime type formats."""
        schema = jsonschema_type("datetime")
        assert schema["type"] == "string"
        assert schema["format"] == "date-time"

    def test_unknown_types(self):
        """Test handling of unknown types."""
        schema = jsonschema_type("CustomType")
        assert schema["type"] == "string"
        assert schema["x-original-type"] == "CustomType"

    def test_empty_and_none(self):
        """Test handling of empty and None inputs."""
        assert jsonschema_type("") == {}
        assert jsonschema_type(None) == {}
        assert jsonschema_type("   ") == {}

    def test_complex_examples(self):
        """Test the examples from the docstring."""
        assert jsonschema_type("int") == {"type": "integer"}
        assert jsonschema_type("List[str]") == {"type": "array", "items": {"type": "string"}}
        assert jsonschema_type("Optional[str]") == {"type": "string"}
        union_schema = jsonschema_type("Union[str, int]")
        assert union_schema["type"] == "string"
        assert "x-original-union" in union_schema
        literal_schema = jsonschema_type("Literal['fast', 'slow']")
        assert literal_schema["type"] == "string"
        assert set(literal_schema["enum"]) == {"fast", "slow"}
        assert jsonschema_type("datetime") == {"type": "string", "format": "date-time"}
        custom_schema = jsonschema_type("CustomType")
        assert custom_schema["type"] == "string"
        assert custom_schema["x-original-type"] == "CustomType"


class TestParseFunctionSignature:
    """Test suite for parse_function_signature function."""

    def test_simple_function(self):
        """Test parsing a simple function."""

        def simple_func(a: int, b: str = "default") -> bool:
            return True

        result = parse_function_signature(simple_func)

        assert result["parameters"]["a"]["type_schema"]["type"] == "integer"
        assert result["parameters"]["a"]["required"] is True
        assert result["parameters"]["b"]["type_schema"]["type"] == "string"
        assert result["parameters"]["b"]["default"] == "default"
        assert result["parameters"]["b"]["required"] is False
        assert result["return_type"]["type"] == "boolean"
        assert result["has_var_args"] is False
        assert result["has_var_kwargs"] is False

    def test_complex_function(self):
        """Test parsing a function with complex types."""
        from typing import Optional

        def complex_func(a: int, b: Optional[str] = None, c: List[int] = None, *args, **kwargs) -> Dict[str, any]:
            return {}

        result = parse_function_signature(complex_func)

        assert result["parameters"]["a"]["type_schema"]["type"] == "integer"
        assert result["parameters"]["b"]["type_schema"]["type"] == "string"
        assert result["parameters"]["c"]["type_schema"]["type"] == "array"
        assert result["has_var_args"] is True
        assert result["has_var_kwargs"] is True

    def test_function_without_annotations(self):
        """Test parsing a function without type annotations."""

        def no_annotations_func(a, b="default"):
            return a + b

        result = parse_function_signature(no_annotations_func)

        assert result["parameters"]["a"]["type_schema"]["type"] == "string"
        assert result["parameters"]["a"]["required"] is True
        assert result["parameters"]["b"]["type_schema"]["type"] == "string"
        assert result["parameters"]["b"]["default"] == "default"
        assert result["parameters"]["b"]["required"] is False

    def test_positional_and_keyword_only_params(self):
        """Test parsing functions with positional-only and keyword-only parameters."""

        def mixed_params_func(a, b, /, c, *, d="keyword"):
            return a + b + c + d

        result = parse_function_signature(mixed_params_func)

        assert result["parameters"]["a"]["positional_only"] is True
        assert result["parameters"]["b"]["positional_only"] is True
        assert "positional_only" not in result["parameters"]["c"]
        assert result["parameters"]["d"]["keyword_only"] is True
        assert result["parameters"]["d"]["default"] == "keyword"

    def test_example_from_docstring(self):
        """Test the example function from the docstring."""

        def example_func(a: int, b: str = "default", c: Optional[float] = None) -> bool:
            """Example function.

            Args:
                a (int): First parameter.
                b (str, optional): Second parameter. Defaults to "default".
                c (Optional[float], optional): Third parameter. Defaults to None.
            """
            return True

        result = parse_function_signature(example_func)

        assert result["parameters"]["a"]["type_schema"]["type"] == "integer"
        assert result["parameters"]["a"]["required"] is True
        assert result["parameters"]["b"]["type_schema"]["type"] == "string"
        assert result["parameters"]["b"]["default"] == "default"
        assert result["parameters"]["b"]["required"] is False
        assert result["return_type"]["type"] == "boolean"


class TestAutotype:
    """Test suite for autotype function."""

    def test_integer_conversion(self):
        """Test integer conversion."""
        assert type(autotype("42")) is int
        assert autotype("42") == 42
        assert type(autotype("-10")) is int
        assert autotype("-10") == -10

    def test_float_conversion(self):
        """Test float conversion."""
        assert type(autotype("3.14")) is float
        assert autotype("3.14") == 3.14
        assert type(autotype("-2.5")) is float
        assert autotype("-2.5") == -2.5

    def test_string_preservation(self):
        """Test that quoted strings remain as strings."""
        assert type(autotype("'42'")) is str
        assert autotype("'42'") == "42"
        assert type(autotype('"hello"')) is str
        assert autotype('"hello"') == "hello"

    def test_boolean_conversion(self):
        """Test boolean conversion."""
        assert autotype("true") is True
        assert autotype("false") is False
        assert autotype("True") is True
        assert autotype("False") is False

    def test_none_conversion(self):
        """Test None conversion."""
        assert autotype("none") is None
        assert autotype("None") is None
        assert autotype("null") is None
        # Case-sensitive for 'Null' - returns as string
        assert autotype("Null") == "Null"

    def test_json_conversion(self):
        """Test JSON conversion."""
        result = autotype('{"key": "value"}')
        assert isinstance(result, dict)
        assert result["key"] == "value"

        result = autotype("[1, 2, 3]")
        assert isinstance(result, list)
        assert result == [1, 2, 3]

    def test_jsonlines_conversion(self):
        """Test JSON lines conversion."""
        # Use actual newlines, not escaped ones
        input_str = '{"a": 1}\n{"b": 2}'
        result = autotype(input_str)
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0] == {"a": 1}
        assert result[1] == {"b": 2}

    def test_expression_evaluation(self):
        """Test expression evaluation."""
        result = autotype("1 + 2")
        assert result == 3

        result = autotype("2 * 3")
        assert result == 6

    def test_string_fallback(self):
        """Test that non-convertible strings remain as strings."""
        result = autotype("Hello, World!")
        assert isinstance(result, str)
        assert result == "Hello, World!"

        result = autotype("not_a_number")
        assert isinstance(result, str)
        assert result == "not_a_number"

    def test_empty_string(self):
        """Test empty string handling."""
        assert autotype("") == ""
        assert autotype("   ") == "   "

    def test_examples_from_docstring(self):
        """Test the examples from the docstring."""
        assert autotype("42") == 42
        assert type(autotype("42")) is int

        assert autotype("3.14") == 3.14
        assert type(autotype("3.14")) is float

        assert autotype("true") is True
        assert autotype("false") is False

        assert autotype("none") is None
        assert autotype("null") is None

        assert autotype("'hello'") == "hello"
        assert autotype('"world"') == "world"

        assert autotype('{"key": "value"}') == {"key": "value"}
        assert autotype("[1, 2, 3]") == [1, 2, 3]

        assert autotype("1 + 2") == 3

        assert autotype("Hello, World!") == "Hello, World!"

    def test_invalid_json(self):
        """Test handling of invalid JSON."""
        # This actually gets evaluated as an expression due to eval
        result = autotype('{"invalid": json}')
        assert isinstance(result, dict)
        assert "invalid" in result
        # The value 'json' refers to the json module
        import json as json_module

        assert result["invalid"] == json_module

    def test_invalid_expression(self):
        """Test handling of invalid expressions."""
        result = autotype("1 + invalid_variable")
        assert isinstance(result, str)
        assert result == "1 + invalid_variable"
