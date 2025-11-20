"""
Unit tests for autotype utility function.

Tests the autotype function which automatically converts string
representations to appropriate Python types.
"""

import pytest
from ahvn.utils.basic.type_utils import autotype


class TestAutotype:
    """Test autotype functionality."""

    @pytest.mark.parametrize(
        "input_str,expected_type,expected_value",
        [
            ("42", int, 42),
            ("3.14", float, 3.14),
            ("true", bool, True),
            ("false", bool, False),
            ("none", type(None), None),
            ("'42'", str, "42"),
            ('"hello"', str, "hello"),
            ('{"key": "value"}', dict, {"key": "value"}),
            ("[1, 2, 3]", list, [1, 2, 3]),
            ("1 + 2", int, 3),
            ("Hello, World!", str, "Hello, World!"),
            ("42.", float, 42.0),
            ("42.0", float, 42.0),
            ("'true'", str, "true"),
            ("'none'", str, "none"),
            ("[true, false, null]", list, [True, False, None]),
            ("[True, False, None]", list, [True, False, None]),
            ("{'a': 1, 'b': 2}", dict, {"a": 1, "b": 2}),
        ],
    )
    def test_autotype_basic_types(self, input_str, expected_type, expected_value):
        """Test autotype conversion for basic data types."""
        result = autotype(input_str)
        assert type(result) is expected_type
        assert result == expected_value

    @pytest.mark.parametrize(
        "input_str,expected",
        [
            ("0", 0),
            ("-42", -42),
            ("3.14159", 3.14159),
            ("-3.14", -3.14),
            ("0.0", 0.0),
            ("1e5", 100000.0),
            ("1e-3", 0.001),
        ],
    )
    def test_autotype_numbers(self, input_str, expected):
        """Test autotype conversion for various number formats."""
        result = autotype(input_str)
        assert result == expected

    @pytest.mark.parametrize(
        "input_str,expected",
        [
            ("True", True),
            ("False", False),
            ("TRUE", True),
            ("FALSE", False),
            ("true", True),
            ("false", False),
            ("1", 1),  # Note: 1 is not converted to True in autotype
            ("0", 0),  # Note: 0 is not converted to False in autotype
        ],
    )
    def test_autotype_booleans(self, input_str, expected):
        """Test autotype conversion for boolean-like strings."""
        result = autotype(input_str)
        assert result == expected

    @pytest.mark.parametrize(
        "input_str,expected",
        [
            ("none", None),
            ("None", None),
        ],
    )
    def test_autotype_none_values(self, input_str, expected):
        """Test autotype conversion for None-like strings."""
        result = autotype(input_str)
        assert result == expected

    def test_autotype_expressions(self):
        """Test autotype conversion for mathematical expressions."""
        assert autotype("1 + 1") == 2
        assert autotype("2 * 3") == 6
        assert autotype("10 / 2") == 5.0
        assert autotype("2 ** 3") == 8
        assert autotype("10 % 3") == 1

    def test_autotype_edge_cases(self):
        """Test autotype conversion for edge cases."""
        # Empty string
        assert autotype("") == ""

        # Whitespace
        assert autotype("   ") == "   "

        # Complex string that looks like code but isn't
        # assert autotype("print('hello')") == "print('hello')"

        # Invalid JSON
        assert autotype("{invalid json}") == "{invalid json}"

        # Invalid expressions
        assert autotype("1 +") == "1 +"
