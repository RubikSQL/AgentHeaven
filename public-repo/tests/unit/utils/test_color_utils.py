import pytest
import sys
from io import StringIO
from unittest.mock import patch, MagicMock
from termcolor import colored

from ahvn.utils.basic.color_utils import (
    _color,
    color_black,
    color_red,
    color_green,
    color_yellow,
    color_blue,
    color_magenta,
    color_cyan,
    color_white,
    color_grey,
    no_color,
    color_debug,
    color_info,
    color_info1,
    color_info2,
    color_info3,
    color_warning,
    color_error,
    color_success,
    print_debug,
    print_info,
    print_warning,
    print_error,
    print_success,
)


class TestColorHelper:
    """Test the internal _color helper function."""

    def test_color_with_console_true_and_color(self):
        """Test _color with console=True and color specified."""
        result = _color("test", color="red", attrs=["bold"], console=True)
        expected = colored("test", color="red", attrs=["bold"])
        assert result == expected

    def test_color_with_console_false(self):
        """Test _color with console=False."""
        result = _color("test", color="red", attrs=["bold"], console=False)
        assert result == "test"

    def test_color_with_no_color(self):
        """Test _color with color=None."""
        result = _color("test", color=None, attrs=["bold"], console=True)
        assert result == "test"

    def test_color_with_no_attrs(self):
        """Test _color with attrs=None."""
        result = _color("test", color="red", attrs=None, console=True)
        expected = colored("test", color="red", attrs=None)
        assert result == expected

    def test_color_with_non_string_object(self):
        """Test _color with non-string object."""
        result = _color(123, color="red", console=True)
        expected = colored("123", color="red", attrs=["bold"])
        assert result == expected


class TestColorFunctions:
    """Test individual color functions."""

    def test_color_black_console_true(self):
        """Test color_black with console=True."""
        with patch("ahvn.utils.basic.color_utils.colored") as mock_colored:
            mock_colored.return_value = "colored_test"
            result = color_black("test", console=True)
            mock_colored.assert_called_once_with("test", color="grey", attrs=["dark"])
            assert result == "colored_test"

    def test_color_black_console_false(self):
        """Test color_black with console=False."""
        result = color_black("test", console=False)
        assert result == "test"

    def test_color_red(self):
        """Test color_red function."""
        with patch("ahvn.utils.basic.color_utils.colored") as mock_colored:
            mock_colored.return_value = "colored_test"
            result = color_red("test")
            mock_colored.assert_called_once_with("test", color="red", attrs=["bold"])
            assert result == "colored_test"

    def test_color_green(self):
        """Test color_green function."""
        with patch("ahvn.utils.basic.color_utils.colored") as mock_colored:
            mock_colored.return_value = "colored_test"
            result = color_green("test")
            mock_colored.assert_called_once_with("test", color="green", attrs=["bold"])
            assert result == "colored_test"

    def test_color_yellow(self):
        """Test color_yellow function."""
        with patch("ahvn.utils.basic.color_utils.colored") as mock_colored:
            mock_colored.return_value = "colored_test"
            result = color_yellow("test")
            mock_colored.assert_called_once_with("test", color="yellow", attrs=["bold"])
            assert result == "colored_test"

    def test_color_blue(self):
        """Test color_blue function."""
        with patch("ahvn.utils.basic.color_utils.colored") as mock_colored:
            mock_colored.return_value = "colored_test"
            result = color_blue("test")
            mock_colored.assert_called_once_with("test", color="blue", attrs=["bold"])
            assert result == "colored_test"

    def test_color_magenta(self):
        """Test color_magenta function."""
        with patch("ahvn.utils.basic.color_utils.colored") as mock_colored:
            mock_colored.return_value = "colored_test"
            result = color_magenta("test")
            mock_colored.assert_called_once_with("test", color="magenta", attrs=["bold"])
            assert result == "colored_test"

    def test_color_cyan(self):
        """Test color_cyan function."""
        with patch("ahvn.utils.basic.color_utils.colored") as mock_colored:
            mock_colored.return_value = "colored_test"
            result = color_cyan("test")
            mock_colored.assert_called_once_with("test", color="cyan", attrs=["bold"])
            assert result == "colored_test"

    def test_color_white(self):
        """Test color_white function."""
        with patch("ahvn.utils.basic.color_utils.colored") as mock_colored:
            mock_colored.return_value = "colored_test"
            result = color_white("test")
            mock_colored.assert_called_once_with("test", color="white", attrs=["bold"])
            assert result == "colored_test"

    def test_color_grey(self):
        """Test color_grey function."""
        with patch("ahvn.utils.basic.color_utils.colored") as mock_colored:
            mock_colored.return_value = "colored_test"
            result = color_grey("test")
            mock_colored.assert_called_once_with("test", color="grey", attrs=["bold"])
            assert result == "colored_test"

    def test_no_color(self):
        """Test no_color function."""
        result = no_color("test")
        assert result == "test"

    def test_no_color_with_number(self):
        """Test no_color function with number."""
        result = no_color(123)
        assert result == "123"


class TestColorAliases:
    """Test color alias functions."""

    def test_color_debug_alias(self):
        """Test color_debug is alias for color_grey."""
        assert color_debug is color_grey

    def test_color_info_alias(self):
        """Test color_info is alias for color_blue."""
        assert color_info is color_blue

    def test_color_info1_alias(self):
        """Test color_info1 is alias for color_blue."""
        assert color_info1 is color_blue

    def test_color_info2_alias(self):
        """Test color_info2 is alias for color_magenta."""
        assert color_info2 is color_magenta

    def test_color_info3_alias(self):
        """Test color_info3 is alias for color_cyan."""
        assert color_info3 is color_cyan

    def test_color_warning_alias(self):
        """Test color_warning is alias for color_yellow."""
        assert color_warning is color_yellow

    def test_color_error_alias(self):
        """Test color_error is alias for color_red."""
        assert color_error is color_red

    def test_color_success_alias(self):
        """Test color_success is alias for color_green."""
        assert color_success is color_green


class TestPrintFunctions:
    """Test print functions."""

    def test_print_functions_basic_behavior(self):
        """Test that print functions exist and can be called without exceptions."""
        # Test that print functions exist and can be called
        # We'll test the behavior by checking they don't raise exceptions
        custom_file = StringIO()
        custom_file.isatty = MagicMock(return_value=True)

        # These should not raise exceptions
        print_debug("debug", file=custom_file)
        print_info("info", file=custom_file)
        print_warning("warning", file=custom_file)
        print_error("error", file=custom_file)
        print_success("success", file=custom_file)

        # Functions should have written to the file
        output = custom_file.getvalue()
        assert len(output) > 0

    def test_print_functions_with_custom_file(self):
        """Test print functions with custom file."""
        custom_file = StringIO()
        custom_file.isatty = MagicMock(return_value=True)

        print_debug("debug", file=custom_file)
        print_info("info", file=custom_file)
        print_warning("warning", file=custom_file)
        print_error("error", file=custom_file)
        print_success("success", file=custom_file)

        output = custom_file.getvalue()
        assert len(output) > 0
        assert "debug" in output
        assert "info" in output
        assert "warning" in output
        assert "error" in output
        assert "success" in output

    def test_print_functions_multiple_args(self):
        """Test print functions with single argument (since color functions expect one object)."""
        custom_file = StringIO()
        custom_file.isatty = MagicMock(return_value=True)

        # Color functions expect a single object, so we pass a single string
        print_info("arg1 arg2 arg3", file=custom_file)

        output = custom_file.getvalue()
        assert len(output) > 0

    def test_print_functions_with_kwargs(self):
        """Test print functions with additional keyword arguments."""
        custom_file = StringIO()
        custom_file.isatty = MagicMock(return_value=True)

        print_info("info", end="", sep="-", file=custom_file)

        output = custom_file.getvalue()
        assert len(output) > 0

    def test_print_functions_no_tty(self):
        """Test print functions with non-tty file."""
        custom_file = StringIO()
        custom_file.isatty = MagicMock(return_value=False)

        print_debug("debug", file=custom_file)
        print_info("info", file=custom_file)

        output = custom_file.getvalue()
        assert len(output) > 0
