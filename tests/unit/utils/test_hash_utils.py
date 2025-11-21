import pytest
from unittest.mock import patch, MagicMock
import sys
import os

from ahvn.utils.basic.hash_utils import (
    md5hash,
    fmt_hash,
    fmt_short_hash,
    _serialize,
)


class TestSerialize:
    """Test the internal _serialize function."""

    def test_serialize_none(self):
        """Test serializing None."""
        result = _serialize(None)
        assert result is None

    def test_serialize_callable_with_module_and_qualname(self):
        """Test serializing a callable with __module__ and __qualname__."""

        def test_func():
            pass

        result = _serialize(test_func)
        expected = f"{test_func.__module__}.{test_func.__qualname__}"
        assert result == expected

    def test_serialize_callable_class_method(self):
        """Test serializing a class method."""

        class TestClass:
            def test_method(self):
                pass

        result = _serialize(TestClass.test_method)
        expected = f"{TestClass.test_method.__module__}.{TestClass.test_method.__qualname__}"
        assert result == expected

    def test_serialize_json_serializable(self):
        """Test serializing JSON-serializable objects."""
        test_data = {"key": "value", "number": 42, "list": [1, 2, 3]}
        result = _serialize(test_data)
        # Should be JSON string with sorted keys
        assert '{"key": "value", "list": [1, 2, 3], "number": 42}' in result

    def test_serialize_json_serializable_sort_keys(self):
        """Test that keys are sorted for deterministic output."""
        test_data = {"z": 1, "a": 2, "m": 3}
        result = _serialize(test_data)
        # Keys should be sorted: a, m, z
        assert result.find('"a"') < result.find('"m"') < result.find('"z"')

    def test_serialize_non_json_fallback_to_repr(self):
        """Test serializing non-JSON objects falls back to repr."""

        class CustomObject:
            def __init__(self, value):
                self.value = value

        obj = CustomObject("test")
        result = _serialize(obj)
        assert result == repr(obj)

    def test_serialize_exception_logging(self):
        """Test that JSON serialization failures are logged."""

        class UnserializableObject:
            def __reduce__(self):
                raise ValueError("Cannot serialize")

        obj = UnserializableObject()

        with patch("ahvn.utils.basic.hash_utils.logger") as mock_logger:
            result = _serialize(obj)
            mock_logger.warning.assert_called_once()
            assert "Failed to JSON serialize object" in mock_logger.warning.call_args[0][0]
            assert result == repr(obj)

    def test_serialize_basic_types(self):
        """Test serializing basic types."""
        assert _serialize("string") == '"string"'
        assert _serialize(42) == "42"
        assert _serialize(3.14) == "3.14"
        assert _serialize(True) == "true"
        assert _serialize(False) == "false"
        assert _serialize([]) == "[]"
        assert _serialize({}) == "{}"

    def test_serialize_nested_structures(self):
        """Test serializing nested structures."""
        test_data = {"nested": {"list": [1, 2, {"inner": "value"}], "tuple": (1, 2, 3)}}
        result = _serialize(test_data)
        assert isinstance(result, str)
        assert "nested" in result
        assert "list" in result


class TestMd5Hash:
    """Test the md5hash function."""

    def test_md5hash_basic_string(self):
        """Test md5hash with a basic string."""
        result = md5hash("test")
        assert isinstance(result, int)
        assert result > 0

    def test_md5hash_with_salt(self):
        """Test md5hash with salt."""
        result1 = md5hash("test", salt="salt1")
        result2 = md5hash("test", salt="salt2")
        assert result1 != result2

    def test_md5hash_without_salt(self):
        """Test md5hash without salt."""
        result = md5hash("test")
        assert isinstance(result, int)
        assert result > 0

    def test_md5hash_none_object(self):
        """Test md5hash with None object."""
        result = md5hash(None)
        assert isinstance(result, int)

    def test_md5hash_none_salt(self):
        """Test md5hash with None salt."""
        result = md5hash("test", salt=None)
        assert isinstance(result, int)

    def test_md5hash_custom_separator(self):
        """Test md5hash with custom separator."""
        result1 = md5hash("test", salt="salt", sep="||")
        result2 = md5hash("test", salt="salt", sep="||")
        result3 = md5hash("test", salt="salt", sep="__")

        assert result1 == result2
        assert result1 != result3

    def test_md5hash_consistent_output(self):
        """Test that md5hash produces consistent output for same input."""
        result1 = md5hash("test", salt="salt", sep="||")
        result2 = md5hash("test", salt="salt", sep="||")
        assert result1 == result2

    def test_md5hash_different_inputs_different_hashes(self):
        """Test that different inputs produce different hashes."""
        result1 = md5hash("test1")
        result2 = md5hash("test2")
        assert result1 != result2

    def test_md5hash_complex_object(self):
        """Test md5hash with complex object."""
        test_obj = {"key": "value", "nested": {"list": [1, 2, 3]}}
        result = md5hash(test_obj)
        assert isinstance(result, int)

    def test_md5hash_callable(self):
        """Test md5hash with callable."""

        def test_func():
            pass

        result = md5hash(test_func)
        assert isinstance(result, int)

    def test_md5hash_numeric_salt(self):
        """Test md5hash with numeric salt."""
        result = md5hash("test", salt=123)
        assert isinstance(result, int)

    def test_md5hash_empty_string(self):
        """Test md5hash with empty string."""
        result = md5hash("")
        assert isinstance(result, int)

    def test_md5hash_large_object(self):
        """Test md5hash with large object."""
        large_obj = {"data": list(range(1000))}
        result = md5hash(large_obj)
        assert isinstance(result, int)


class TestFmtHash:
    """Test the fmt_hash function."""

    def test_fmt_hash_none_input(self):
        """Test fmt_hash with None input."""
        result = fmt_hash(None)
        assert result is None

    def test_fmt_hash_integer_input(self):
        """Test fmt_hash with integer input."""
        result = fmt_hash(123)
        assert result == "0000000000000000000000000000000000000123"
        assert len(result) == 40

    def test_fmt_hash_string_input(self):
        """Test fmt_hash with string input."""
        result = fmt_hash("test_string")
        assert result == "test_string"

    def test_fmt_hash_integer_string_representation(self):
        """Test fmt_hash with string representation of integer."""
        result = fmt_hash("123")
        assert result == "123"

    def test_fmt_hash_zero_padding(self):
        """Test fmt_hash zero padding for small numbers."""
        result = fmt_hash(1)
        assert result == "0000000000000000000000000000000000000001"
        assert len(result) == 40

    def test_fmt_hash_large_number(self):
        """Test fmt_hash with large number."""
        large_num = 1234567890123456789012345678901234567890
        result = fmt_hash(large_num)
        assert result == str(large_num)

    def test_fmt_hash_float_input(self):
        """Test fmt_hash with float input - should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            fmt_hash(3.14)
        assert "Unknown format code 'd' for object of type 'float'" in str(exc_info.value)

    def test_fmt_hash_negative_number(self):
        """Test fmt_hash with negative number."""
        result = fmt_hash(-123)
        # The actual behavior is that negative numbers get 39 zeros after the minus sign
        assert result == "-000000000000000000000000000000000000123"
        assert len(result) == 40

    def test_fmt_hash_zero(self):
        """Test fmt_hash with zero."""
        result = fmt_hash(0)
        assert result == "0000000000000000000000000000000000000000"
        assert len(result) == 40


class TestFmtShortHash:
    """Test the fmt_short_hash function."""

    def test_fmt_short_hash_none_input(self):
        """Test fmt_short_hash with None input."""
        result = fmt_short_hash(None)
        assert result is None

    def test_fmt_short_hash_integer_input_default_length(self):
        """Test fmt_short_hash with integer input and default length."""
        result = fmt_short_hash(123)
        assert result == "00000123"
        assert len(result) == 8

    def test_fmt_short_hash_string_input(self):
        """Test fmt_short_hash with string input."""
        result = fmt_short_hash("test_string")
        # Should return the last 8 characters (default length)
        assert result == "t_string"
        assert len(result) == 8

    def test_fmt_short_hash_custom_length(self):
        """Test fmt_short_hash with custom length."""
        result = fmt_short_hash(123, length=5)
        assert result == "00123"
        assert len(result) == 5

    def test_fmt_short_hash_zero_with_default_length(self):
        """Test fmt_short_hash with zero and default length."""
        result = fmt_short_hash(0)
        assert result == "00000000"
        assert len(result) == 8

    def test_fmt_short_hash_large_number_modulo(self):
        """Test fmt_short_hash with large number that needs modulo operation."""
        # Test with a number larger than 10^8
        large_num = 1234567890
        result = fmt_short_hash(large_num)
        # Should be 1234567890 % 10^8 = 34567890
        assert result == "34567890"
        assert len(result) == 8

    def test_fmt_short_hash_large_number_custom_length(self):
        """Test fmt_short_hash with large number and custom length."""
        large_num = 123456
        result = fmt_short_hash(large_num, length=4)
        # Should be 123456 % 10^4 = 3456
        assert result == "3456"
        assert len(result) == 4

    def test_fmt_short_hash_negative_number(self):
        """Test fmt_short_hash with negative number."""
        result = fmt_short_hash(-123)
        # -123 % 10^8 = 99999877 (Python's modulo behavior with negatives)
        assert result == "99999877"
        assert len(result) == 8

    def test_fmt_short_hash_string_integer_representation(self):
        """Test fmt_short_hash with string representation of integer."""
        result = fmt_short_hash("123")
        # Should return the last 8 characters (default length), but since "123" is only 3 chars, returns "123"
        assert result == "123"

    def test_fmt_short_hash_length_one(self):
        """Test fmt_short_hash with length of 1."""
        result = fmt_short_hash(123, length=1)
        # 123 % 10^1 = 3
        assert result == "3"
        assert len(result) == 1

    def test_fmt_short_hash_zero_custom_length(self):
        """Test fmt_short_hash with zero and custom length."""
        result = fmt_short_hash(0, length=12)
        assert result == "000000000000"
        assert len(result) == 12

    def test_fmt_short_hash_consistent_output(self):
        """Test that fmt_short_hash produces consistent output for same input."""
        result1 = fmt_short_hash(12345, length=6)
        result2 = fmt_short_hash(12345, length=6)
        assert result1 == result2
        assert result1 == "012345"

    def test_fmt_short_hash_string_longer_than_length(self):
        """Test fmt_short_hash with string longer than specified length."""
        result = fmt_short_hash("very_long_string", length=5)
        # Should return the last 5 characters
        assert result == "tring"
        assert len(result) == 5

    def test_fmt_short_hash_string_shorter_than_length(self):
        """Test fmt_short_hash with string shorter than specified length."""
        result = fmt_short_hash("abc", length=8)
        # Should return the full string since it's shorter than length
        assert result == "abc"
        assert len(result) == 3

    def test_fmt_short_hash_string_custom_length(self):
        """Test fmt_short_hash with string and custom length."""
        result = fmt_short_hash("test_string_example", length=10)
        # Should return the last 10 characters
        assert result == "ng_example"
        assert len(result) == 10

    def test_fmt_short_hash_empty_string(self):
        """Test fmt_short_hash with empty string."""
        result = fmt_short_hash("", length=8)
        assert result == ""
        assert len(result) == 0


class TestIntegration:
    """Integration tests for hash_utils."""

    def test_md5hash_and_fmt_hash_together(self):
        """Test using md5hash and fmt_hash together."""
        hash_val = md5hash("test", salt="salt")
        formatted = fmt_hash(hash_val)

        assert isinstance(hash_val, int)
        assert isinstance(formatted, str)
        assert len(formatted) == 40
        assert formatted.isdigit() or formatted.lstrip("-").isdigit()

    def test_consistent_hashing_across_calls(self):
        """Test that hashing is consistent across multiple calls."""
        test_data = {"key": "value", "number": 42}

        hashes = []
        for _ in range(5):
            hash_val = md5hash(test_data)
            hashes.append(hash_val)

        # All hashes should be the same
        assert all(h == hashes[0] for h in hashes)

    def test_different_objects_different_hashes(self):
        """Test that different objects produce different hashes."""
        objects = [
            "string1",
            "string2",
            {"key": "value"},
            {"key": "value2"},
            [1, 2, 3],
            [1, 2, 4],
        ]

        hashes = [md5hash(obj) for obj in objects]

        # All hashes should be different
        assert len(set(hashes)) == len(hashes)

    def test_md5hash_and_fmt_short_hash_together(self):
        """Test using md5hash and fmt_short_hash together."""
        hash_val = md5hash("test", salt="salt")
        formatted = fmt_short_hash(hash_val)

        assert isinstance(hash_val, int)
        assert isinstance(formatted, str)
        assert len(formatted) == 8
        assert formatted.isdigit()

    def test_md5hash_and_fmt_short_hash_custom_length(self):
        """Test using md5hash and fmt_short_hash with custom length."""
        hash_val = md5hash({"key": "value"})
        formatted = fmt_short_hash(hash_val, length=12)

        assert isinstance(hash_val, int)
        assert isinstance(formatted, str)
        assert len(formatted) == 12
        assert formatted.isdigit()
