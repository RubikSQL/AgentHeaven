__all__ = [
    "color_black",
    "color_red",
    "color_green",
    "color_yellow",
    "color_blue",
    "color_magenta",
    "color_cyan",
    "color_white",
    "color_grey",
    "no_color",
    "color_debug",
    "color_info",
    "color_info1",
    "color_info2",
    "color_info3",
    "color_warning",
    "color_error",
    "color_success",
    "print_debug",
    "print_info",
    "print_warning",
    "print_error",
    "print_success",
]

from sys import stderr
from typing import Any, Callable, Optional, List, Dict
from termcolor import colored


def _color(obj: Any, color: Optional[str] = None, attrs: Optional[List[str]] = None, console: bool = True) -> str:
    """\
    Internal helper to colorize a string using termcolor.

    Args:
        obj (Any): The object to convert to string and colorize.
        color (Optional[str]): The color name.
        attrs (Optional[list[str]]): List of attributes (e.g., ['bold']).
        console (bool): Whether to apply color (True) or return plain string (False).

    Returns:
        str: The colorized string.
    """
    s = str(obj)
    if not console or color is None:
        return s
    return colored(s, color=color, attrs=attrs)


def color_black(obj: Any, console: bool = True) -> str:
    """\
    Return the string in black (grey/dark) color.

    Args:
        obj (Any): The object to colorize.
        console (bool): Whether to apply color.

    Returns:
        str: The colorized string.
    """
    return _color(obj, color="grey", attrs=["dark"], console=console)


def color_red(obj: Any, console: bool = True) -> str:
    """\
    Return the string in red color.

    Args:
        obj (Any): The object to colorize.
        console (bool): Whether to apply color.

    Returns:
        str: The colorized string.
    """
    return _color(obj, color="red", attrs=["bold"], console=console)


def color_green(obj: Any, console: bool = True) -> str:
    """\
    Return the string in green color.

    Args:
        obj (Any): The object to colorize.
        console (bool): Whether to apply color.

    Returns:
        str: The colorized string.
    """
    return _color(obj, color="green", attrs=["bold"], console=console)


def color_yellow(obj: Any, console: bool = True) -> str:
    """\
    Return the string in yellow color.

    Args:
        obj (Any): The object to colorize.
        console (bool): Whether to apply color.

    Returns:
        str: The colorized string.
    """
    return _color(obj, color="yellow", attrs=["bold"], console=console)


def color_blue(obj: Any, console: bool = True) -> str:
    """\
    Return the string in blue color.

    Args:
        obj (Any): The object to colorize.
        console (bool): Whether to apply color.

    Returns:
        str: The colorized string.
    """
    return _color(obj, color="blue", attrs=["bold"], console=console)


def color_magenta(obj: Any, console: bool = True) -> str:
    """\
    Return the string in magenta color.

    Args:
        obj (Any): The object to colorize.
        console (bool): Whether to apply color.

    Returns:
        str: The colorized string.
    """
    return _color(obj, color="magenta", attrs=["bold"], console=console)


def color_cyan(obj: Any, console: bool = True) -> str:
    """\
    Return the string in cyan color.

    Args:
        obj (Any): The object to colorize.
        console (bool): Whether to apply color.

    Returns:
        str: The colorized string.
    """
    return _color(obj, color="cyan", attrs=["bold"], console=console)


def color_white(obj: Any, console: bool = True) -> str:
    """\
    Return the string in white color.

    Args:
        obj (Any): The object to colorize.
        console (bool): Whether to apply color.

    Returns:
        str: The colorized string.
    """
    return _color(obj, color="white", attrs=["bold"], console=console)


def color_grey(obj: Any, console: bool = True) -> str:
    """\
    Return the string in grey color.

    Args:
        obj (Any): The object to colorize.
        console (bool): Whether to apply color.

    Returns:
        str: The colorized string.
    """
    return _color(obj, color="grey", attrs=["bold"], console=console)


def no_color(obj: Any, console: bool = True) -> str:
    """\
    Return the string without any color.

    Args:
        obj (Any): The object to convert to string.
        console (bool): Ignored.

    Returns:
        str: The plain string.
    """
    return str(obj)


color_debug = color_grey
color_info = color_blue
color_info1 = color_blue
color_info2 = color_magenta
color_info3 = color_cyan
color_warning = color_yellow
color_error = color_red
color_success = color_green


def print_debug(*args, **kwargs):
    """\
    Print debug messages in grey color to stderr (unless otherwise specified in `file`).

    Args:
        *args: Arguments to print.
        **kwargs: Keyword arguments for print.
    """
    file = kwargs.get("file", stderr)
    others = {k: v for k, v in kwargs.items() if k != "file"}
    console = hasattr(file, "isatty") and file.isatty()
    print(color_debug(*args, console=console), file=file, **others)


def print_info(*args, **kwargs):
    """\
    Print info messages in blue color to stderr (unless otherwise specified in `file`).

    Args:
        *args: Arguments to print.
        **kwargs: Keyword arguments for print.
    """
    file = kwargs.get("file", stderr)
    others = {k: v for k, v in kwargs.items() if k != "file"}
    console = hasattr(file, "isatty") and file.isatty()
    print(color_info(*args, console=console), file=file, **others)


def print_warning(*args, **kwargs):
    """\
    Print warning messages in yellow color to stderr (unless otherwise specified in `file`).

    Args:
        *args: Arguments to print.
        **kwargs: Keyword arguments for print.
    """
    file = kwargs.get("file", stderr)
    others = {k: v for k, v in kwargs.items() if k != "file"}
    console = hasattr(file, "isatty") and file.isatty()
    print(color_warning(*args, console=console), file=file, **others)


def print_error(*args, **kwargs):
    """\
    Print error messages in red color to stderr (unless otherwise specified in `file`).

    Args:
        *args: Arguments to print.
        **kwargs: Keyword arguments for print.
    """
    file = kwargs.get("file", stderr)
    others = {k: v for k, v in kwargs.items() if k != "file"}
    console = hasattr(file, "isatty") and file.isatty()
    print(color_error(*args, console=console), file=file, **others)


def print_success(*args, **kwargs):
    """\
    Print success messages in green color to stderr (unless otherwise specified in `file`).

    Args:
        *args: Arguments to print.
        **kwargs: Keyword arguments for print.
    """
    file = kwargs.get("file", stderr)
    others = {k: v for k, v in kwargs.items() if k != "file"}
    console = hasattr(file, "isatty") and file.isatty()
    print(color_success(*args, console=console), file=file, **others)
