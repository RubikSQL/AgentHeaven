__all__ = [
    "pj",
    "get_file_ext",
    "get_file_name",
    "get_file_basename",
    "get_file_dir",
    "has_file_ext",
]

import re
import os
from typing import Union, List


def pj(*args: List[str], abs: bool = False) -> str:
    """\
    Join a list of strings into a path. Platform-agnostic and user-expanding. Spaces and trailing slashes are stripped from each argument.

    Args:
        *args: Components of the path to join. Each argument should be a string.
        abs (bool, optional): If True, returns the absolute path. Defaults to False.

    Returns:
        str: The joined, normalized path. Expands '~' to the user's home directory.
    """
    args = [arg.rstrip(" /").strip() for arg in args if arg.rstrip(" /").strip()]
    if not args:
        return "/"
    path = os.path.expanduser(os.path.join(*[arg for arg in args if arg]))
    return os.path.normpath(path if not abs else os.path.abspath(path))


def get_file_ext(path: str) -> str:
    """\
    Get the file extension (without a dot) for a specified path.

    Args:
        path (str): The path to the file.

    Returns:
        str: The file extension without a dot.
    """
    ext = os.path.splitext(pj(path, abs=True))[1]
    return ext[1:] if ext.startswith(".") else ext


def get_file_name(path: str, ext: Union[bool, str] = True, abs: bool = False) -> str:
    """\
    Get the full file name from the specified path. When a file extension is provided (preferrably without a dot), it will be used instead of the file's original extension.

    Args:
        path: str: The path to the file.
        ext: Union[bool, str]: If True, returns the file name with its original extension. If False, returns the file name without any extension. If a string is provided, it will be used as the new extension.
        abs: bool: If True, returns the absolute path. Defaults to False.

    Returns:
        str: The file name with or without the specified extension.

    Examples:
        >>> get_file_name("A/B/C/file.txt")
        'A/B/C/file.txt'
        >>> get_file_name("A/B/C/file.txt", ext=True)
        'A/B/C/file.txt'
        >>> get_file_name("A/B/C/file.txt", ext=False)
        'A/B/C/file'
        >>> get_file_name("A/B/C/file.txt", ext="md")
        'A/B/C/file.md'
        >>> get_file_name("A/B/C/")
        'C'
    """
    path = pj(path, abs=abs)
    pfx, _ = os.path.splitext(path)
    if not ext:
        return pfx
    if ext is True:
        return path
    return pfx + ("" if ext.startswith(".") else ".") + ext


def get_file_basename(path: str, ext: Union[bool, str] = True) -> str:
    """\
    Get the base name of the file from the specified path. When a file extension is provided (preferably without a dot), it will be used instead of the file's original extension.

    Args:
        path (str): The path to the file.
        ext (Union[bool, str]): If True, returns the file name with its original extension. If False, returns the file name without any extension. If a string is provided, it will be used as the new extension.

    Returns:
        str: The base name of the file.

    Examples:
        >>> get_file_basename("A/B/C/file.txt")
        'file.txt'
        >>> get_file_basename("A/B/C/file.txt", ext=True)
        'file.txt'
        >>> get_file_basename("A/B/C/file.txt", ext=False)
        'file'
        >>> get_file_basename("A/B/C/file.txt", ext="md")
        'file.md'
    """
    return os.path.basename(get_file_name(path, ext=ext, abs=True))


def get_file_dir(path: str, abs: bool = False) -> str:
    """\
    Get the directory of the specified file path.

    Args:
        path (str): The path to the file.
        abs (bool): If True, returns the absolute path. Defaults to False.

    Returns:
        str: The directory of the file.

    Examples:
        >>> get_file_dir("A/B/C/file.txt")
        'A/B/C'
        >>> get_file_dir("/")
        '/'
    """
    return os.path.dirname(pj(path, abs=abs))


def has_file_ext(path: str, ext: Union[None, str, List[str]] = None) -> bool:
    """\
    Check if the specified file path has a given extension or any of the extensions in a list.

    Args:
        path (str): The path to the file.
        ext (Union[None, str, List[str]]): The extension to check for. If `None`, return whether the file has any extension. If a string, checks for that specific extension. A string may contain multiple extensions separated by commas or semicolons, which will be split into a list. If a list, checks if the file has any of the extensions in the list. Each list item may be `None`, which will check if the file has NO extension, or a string, which will check for that specific extension (preferably without a dot).

    Returns:
        bool: True if the file has the specified extension(s), False otherwise.

    Examples:
        >>> has_file_ext("A/B/C/file.txt", ext="txt")
        True
        >>> has_file_ext("A/B/C/file.txt", ext="md")
        False
        >>> has_file_ext("A/B/C/file.txt", ext=["txt", "md"])
        True
        >>> has_file_ext("A/B/C/file.txt", ext=None)
        True
        >>> has_file_ext("A/B/C/file", ext=None)
        False
        >>> has_file_ext("A/B/C/file", ext=[None, "txt,md;py"])
        True
    """
    if ext is None:
        return bool(get_file_ext(path))
    if isinstance(ext, str):
        ext = [ext]
    if (None in ext) and get_file_ext(path):
        return True
    ext = set(e for e in ext if e is not None)
    ext = set(e.strip() for expr in ext for e in re.split(r"[;,]", expr) if e.strip())
    ext = set(e[1:] if e.startswith(".") else e for e in ext if e.strip())
    return bool(get_file_ext(path) in ext)
