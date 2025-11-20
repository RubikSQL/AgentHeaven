import pytest
import sys
from unittest.mock import patch, MagicMock
from io import StringIO

from ahvn.utils.basic.debug_utils import (
    raise_mismatch,
    error_str,
    FunctionDeserializationError,
    LLMError,
    ToolError,
    DatabaseError,
    AutoFuncError,
    DependencyError,
)


class TestRaiseMismatch:
    """Test the raise_mismatch function."""

    def test_value_in_supported_list(self):
        """Test when the value is in the supported list."""
        supported = ["apple", "banana", "cherry"]
        result = raise_mismatch(supported, "apple")
        assert result == "apple"

    def test_value_not_in_supported_list_with_suggestion(self):
        """Test when the value is not in the supported list but has a close match."""
        supported = ["apple", "banana", "cherry"]
        result = raise_mismatch(supported, "aple", mode="ignore")
        assert result == "apple"

    def test_value_not_in_supported_list_no_suggestion(self):
        """Test when the value is not in the supported list and no close match."""
        supported = ["apple", "banana", "cherry"]
        result = raise_mismatch(supported, "xyz", mode="ignore")
        assert result is None

    def test_mode_warn_with_suggestion(self):
        """Test mode 'warn' with a suggestion."""
        supported = ["apple", "banana", "cherry"]
        with patch("ahvn.utils.basic.debug_utils.logger") as mock_logger:
            result = raise_mismatch(supported, "aple", mode="warn")
            assert result == "apple"
            mock_logger.warning.assert_called_once()

    def test_mode_warn_no_suggestion(self):
        """Test mode 'warn' without a suggestion."""
        supported = ["apple", "banana", "cherry"]
        with patch("ahvn.utils.basic.debug_utils.logger") as mock_logger:
            result = raise_mismatch(supported, "xyz", mode="warn")
            assert result is None
            mock_logger.warning.assert_called_once()

    def test_mode_exit_with_suggestion(self):
        """Test mode 'exit' with a suggestion."""
        supported = ["apple", "banana", "cherry"]
        with patch("ahvn.utils.basic.debug_utils.logger") as mock_logger:
            with patch("builtins.exit") as mock_exit:
                raise_mismatch(supported, "aple", mode="exit")
                mock_logger.error.assert_called_once()
                mock_exit.assert_called_once_with(1)

    def test_mode_exit_no_suggestion(self):
        """Test mode 'exit' without a suggestion."""
        supported = ["apple", "banana", "cherry"]
        with patch("ahvn.utils.basic.debug_utils.logger") as mock_logger:
            with patch("builtins.exit") as mock_exit:
                raise_mismatch(supported, "xyz", mode="exit")
                mock_logger.error.assert_called_once()
                mock_exit.assert_called_once_with(1)

    def test_mode_raise_with_suggestion(self):
        """Test mode 'raise' with a suggestion."""
        supported = ["apple", "banana", "cherry"]
        with pytest.raises(ValueError) as exc_info:
            raise_mismatch(supported, "aple", mode="raise")
        assert "Did you mean 'apple'?" in str(exc_info.value)
        assert "Unsupported value 'aple'" in str(exc_info.value)

    def test_mode_raise_no_suggestion(self):
        """Test mode 'raise' without a suggestion."""
        supported = ["apple", "banana", "cherry"]
        with pytest.raises(ValueError) as exc_info:
            raise_mismatch(supported, "xyz", mode="raise")
        assert "Did you mean" not in str(exc_info.value)
        assert "Unsupported value 'xyz'" in str(exc_info.value)

    def test_custom_name_parameter(self):
        """Test with custom name parameter."""
        supported = ["apple", "banana", "cherry"]
        with pytest.raises(ValueError) as exc_info:
            raise_mismatch(supported, "aple", name="fruit", mode="raise")
        assert "Unsupported fruit 'aple'" in str(exc_info.value)

    def test_custom_comment_parameter(self):
        """Test with custom comment parameter."""
        supported = ["apple", "banana", "cherry"]
        with pytest.raises(ValueError) as exc_info:
            raise_mismatch(supported, "aple", comment="Please check your input", mode="raise")
        assert "Please check your input" in str(exc_info.value)

    def test_custom_threshold_parameter(self):
        """Test with custom threshold parameter."""
        supported = ["apple", "banana", "cherry"]
        # Very low threshold should still find a match
        result = raise_mismatch(supported, "aple", mode="ignore", thres=0.1)
        assert result == "apple"

        # Very high threshold should not find a match
        result = raise_mismatch(supported, "aple", mode="ignore", thres=0.9)
        assert result is None

    def test_empty_supported_list(self):
        """Test with empty supported list."""
        supported = []
        with pytest.raises(ValueError) as exc_info:
            raise_mismatch(supported, "test", mode="raise")
        assert "Available options: none" in str(exc_info.value)

    def test_numeric_values(self):
        """Test with numeric values."""
        supported = [1, 2, 3]
        result = raise_mismatch(supported, 1)
        assert result == 1

        result = raise_mismatch(supported, 4, mode="ignore")
        assert result is None

    def test_mixed_types(self):
        """Test with mixed types in supported list."""
        supported = ["apple", 1, True]
        result = raise_mismatch(supported, "apple")
        assert result == "apple"

        result = raise_mismatch(supported, 1)
        assert result == 1

    def test_invalid_mode_recursive_call(self):
        """Test that invalid mode raises an error recursively."""
        supported = ["apple", "banana", "cherry"]
        with pytest.raises(ValueError) as exc_info:
            raise_mismatch(supported, "aple", mode="invalid_mode")
        assert "Unsupported mode 'invalid_mode'" in str(exc_info.value)

    def test_similarity_threshold_edge_cases(self):
        """Test similarity threshold edge cases."""
        supported = ["apple", "banana", "cherry"]

        # Exact threshold match
        with patch("ahvn.utils.basic.debug_utils.SequenceMatcher") as mock_matcher:
            mock_instance = MagicMock()
            mock_instance.ratio.return_value = 0.3
            mock_matcher.return_value = mock_instance
            result = raise_mismatch(supported, "aple", mode="ignore", thres=0.3)
            assert result == "apple"

        # Just below threshold
        with patch("ahvn.utils.basic.debug_utils.SequenceMatcher") as mock_matcher:
            mock_instance = MagicMock()
            mock_instance.ratio.return_value = 0.299
            mock_matcher.return_value = mock_instance
            result = raise_mismatch(supported, "aple", mode="ignore", thres=0.3)
            assert result is None


class TestErrorStr:
    """Test the error_str function."""

    def test_none_input(self):
        """Test with None input."""
        result = error_str(None)
        assert result is None

    def test_string_input(self):
        """Test with string input."""
        result = error_str("  test error  ")
        assert result == "test error"

    def test_exception_with_traceback(self):
        """Test with Exception and traceback=True."""
        try:
            raise ValueError("test error")
        except ValueError as e:
            result = error_str(e, tb=True)
            assert "ValueError: test error" in result
            assert "Traceback" in result

    def test_exception_without_traceback(self):
        """Test with Exception and traceback=False."""
        try:
            raise ValueError("test error")
        except ValueError as e:
            result = error_str(e, tb=False)
            assert result == "test error"

    def test_exception_default_traceback(self):
        """Test with Exception and default traceback (True)."""
        try:
            raise ValueError("test error")
        except ValueError as e:
            result = error_str(e)
            assert "ValueError: test error" in result
            assert "Traceback" in result

    def test_non_exception_object(self):
        """Test with non-exception object."""
        result = error_str(123)
        assert result == "123"

    def test_custom_exception(self):
        """Test with custom exception."""

        class CustomError(Exception):
            pass

        try:
            raise CustomError("custom error")
        except CustomError as e:
            result = error_str(e, tb=False)
            assert result == "custom error"

    def test_exception_with_multiline_message(self):
        """Test with exception that has multiline message."""
        try:
            raise ValueError("line 1\nline 2\nline 3")
        except ValueError as e:
            result = error_str(e, tb=False)
            assert result == "line 1\nline 2\nline 3"

    def test_exception_with_args(self):
        """Test with exception that has multiple args."""
        try:
            raise ValueError("error", 123, "extra")
        except ValueError as e:
            result = error_str(e, tb=False)
            # The string representation includes all args
            assert "error" in result


class TestCustomExceptions:
    """Test custom exception classes."""

    def test_function_deserialization_error(self):
        """Test FunctionDeserializationError exception."""
        with pytest.raises(FunctionDeserializationError):
            raise FunctionDeserializationError("test")

    def test_llm_error(self):
        """Test LLMError exception."""
        with pytest.raises(LLMError):
            raise LLMError("test")

    def test_tool_error(self):
        """Test ToolError exception."""
        with pytest.raises(ToolError):
            raise ToolError("test")

    def test_db_error(self):
        """Test DatabaseError exception."""
        with pytest.raises(DatabaseError):
            raise DatabaseError("test")

    def test_autofunc_error(self):
        """Test AutoFuncError exception."""
        with pytest.raises(AutoFuncError):
            raise AutoFuncError("test")

    def test_dependency_error_inheritance(self):
        """Test DependencyError inherits from ImportError."""
        assert issubclass(DependencyError, ImportError)
        with pytest.raises(DependencyError):
            raise DependencyError("test")
        with pytest.raises(ImportError):
            raise DependencyError("test")

    def test_custom_exceptions_with_messages(self):
        """Test all custom exceptions with custom messages."""
        exceptions = [
            FunctionDeserializationError,
            LLMError,
            ToolError,
            DatabaseError,
            AutoFuncError,
            DependencyError,
        ]

        for exc_class in exceptions:
            with pytest.raises(exc_class) as exc_info:
                raise exc_class("test message")
            assert str(exc_info.value) == "test message"

    def test_custom_exceptions_without_messages(self):
        """Test all custom exceptions without messages."""
        exceptions = [
            FunctionDeserializationError,
            LLMError,
            ToolError,
            DatabaseError,
            AutoFuncError,
            DependencyError,
        ]

        for exc_class in exceptions:
            with pytest.raises(exc_class):
                raise exc_class()
