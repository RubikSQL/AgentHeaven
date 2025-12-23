__all__ = [
    "touch_file",
    "touch_dir",
    "exists_file",
    "exists_dir",
    "exists_path",
    "list_files",
    "list_dirs",
    "list_paths",
    "enum_files",
    "enum_dirs",
    "enum_paths",
    "empty_dir",
    "nonempty_dir",
    "copy_file",
    "copy_dir",
    "copy_path",
    "delete_file",
    "delete_dir",
    "delete_path",
    "folder_diagram",
]

from .path_utils import *
from .config_utils import HEAVEN_CM, hpj

_encoding = HEAVEN_CM.get("core.encoding", "utf-8")

import os
import shutil
from typing import Union, List, Generator, Literal, Dict, Optional


def touch_file(path: str, encoding: str = None, clear: bool = False, content: Optional[str] = None) -> str:
    """\
    Create an empty file at the specified path, or write content to it.

    Warning:
        An extra newline will be added at the end of the string to be consistent with the behavior of `save_txt` and `append_txt`.

    Args:
        path (str): The file path to create.
        encoding (str, optional): Encoding to use for the file. Defaults to None.
        clear (bool, optional): If True, clears the file if it exists. If False, do nothing if the file exists. Defaults to False.
        content (str, optional): Content to write to the file (overwrite existing content). Only works if `ckear` is True or the file does not exist.
            Notice that an empty string `content=""` is different from `content=None`, the former writes a linebreak to the file, while the latter creates an empty file.
            Defaults to None, which creates an empty file.

    Returns:
        path (str): The path to the created or cleared file.

    Raises:
        ValueError: If the path exists and is not a file.
    """
    path = hpj(path, abs=True)
    if os.path.dirname(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        if not os.path.isfile(path):
            raise FileExistsError(f"Path {path} exists and is not a file.")
        if not clear:
            return path
    with open(path, "w", encoding=encoding or _encoding, errors="ignore") as fp:
        if content is not None:
            fp.write(str(content) + "\n")
    return path


def touch_dir(path: str, clear: bool = False) -> str:
    """\
    Create an empty directory at the specified path.

    Args:
        path (str): The directory path to create.
        clear (bool, optional): If True, clears the directory if it exists. If False, do nothing if the directory exists. Defaults to False.

    Returns:
        path (str): The path to the created or cleared directory.
    """
    path = hpj(path, abs=True)
    if clear and os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)
    return path


def exists_file(path: str) -> bool:
    """\
    Check if a file exists at the specified path.

    Args:
        path (str): The file path to check.

    Returns:
        bool: True if the file exists, False otherwise.
    """
    path = hpj(path, abs=True)
    return os.path.exists(path) and os.path.isfile(path)


def exists_dir(path: str) -> bool:
    """\
    Check if a directory exists at the specified path.

    Args:
        path (str): The directory path to check.

    Returns:
        bool: True if the directory exists, False otherwise.
    """
    path = hpj(path, abs=True)
    return os.path.exists(path) and os.path.isdir(path)


def exists_path(path: str) -> bool:
    """\
    Check if a path exists at the specified path.

    Args:
        path (str): The path to check.

    Returns:
        bool: True if the path exists, False otherwise.
    """
    path = hpj(path, abs=True)
    return os.path.exists(path)


def list_files(path: str, ext: Union[None, str, List[str]] = None, abs: bool = False) -> Generator[str, None, None]:
    """\
    List all files in the specified directory with optional extension filtering.
    Guarantees an alphabetical sorted order (case-insensitive) of files.

    Args:
        path (str): The directory path to list files from.
        ext (Union[str, List[str]]): The extension to check for. If `None`, return all files. If a string, checks for that specific extension. A string may contain multiple extensions separated by commas or semicolons, which will be split into a list. If a list, checks if the file has any of the extensions in the list. Each list item should be a string, which will check for that specific extension (preferably without a dot). Repeated extensions does NOT result in repeated files.
        abs (bool, optional): If True, return absolute paths. Defaults to False.

    Yields:
        str: The file paths that match the criteria.
    """
    path = hpj(path, abs=True)
    if not exists_dir(path):
        return
    entries = list()
    for entry in os.scandir(path):
        if entry.is_file() and has_file_ext(entry.path, ext=ext):
            entries.append(os.path.abspath(entry.path) if abs else os.path.relpath(entry.path, path))
    yield from sorted(entries, key=lambda name: name.lower())
    return


def list_dirs(path: str, abs: bool = False) -> Generator[str, None, None]:
    """\
    List all directories in the specified directory.
    Guarantees an alphabetical sorted order (case-insensitive) of directories.

    Args:
        path (str): The directory path to list directories from.
        abs (bool, optional): If True, return absolute paths. Defaults to False.

    Yields:
        str: The directory paths.
    """
    path = hpj(path, abs=True)
    if not exists_dir(path):
        return
    entries = list()
    for entry in os.scandir(path):
        if entry.is_dir():
            entries.append(os.path.abspath(entry.path) if abs else os.path.relpath(entry.path, path))
    yield from sorted(entries, key=lambda name: name.lower())
    return


def list_paths(path: str, ext: Union[None, str, List[str]] = None, abs: bool = False) -> Generator[str, None, None]:
    """\
    List all directories and files in the specified directory with optional extension filtering.
    Directories are always listed before files. Guarantees an alphabetical sorted order (case-insensitive) of files.

    Args:
        path (str): The directory path to list paths from.
        ext (Union[str, List[str]]): The extension to check for. If `None`, return all files. If a string, checks for that specific extension. A string may contain multiple extensions separated by commas or semicolons, which will be split into a list. If a list, checks if the file has any of the extensions in the list. Each list item should be a string, which will check for that specific extension (preferably without a dot). Repeated extensions does NOT result in repeated files.
        abs (bool, optional): If True, return absolute paths. Defaults to False.

    Yields:
        str: The file and directory paths that match the criteria.
    """
    yield from list_dirs(path, abs=abs)
    yield from list_files(path, ext=ext, abs=abs)
    return


def enum_files(path: str, ext: Union[None, str, List[str]] = None, abs: bool = False) -> Generator[str, None, None]:
    """\
    Enumerate all files in the specified directory with optional extension filtering.
    Guarantees an alphabetical sorted order (case-insensitive) of files.

    Args:
        path (str): The directory path to enumerate files from.
        ext (Union[str, List[str]]): The extension to check for. If `None`, return all files. If a string, checks for that specific extension. A string may contain multiple extensions separated by commas or semicolons, which will be split into a list. If a list, checks if the file has any of the extensions in the list. Each list item should be a string, which will check for that specific extension (preferably without a dot). Repeated extensions does NOT result in repeated files.
        abs (bool, optional): If True, return absolute paths. Defaults to False.

    Yields:
        str: The file path and its base name.
    """
    path = hpj(path, abs=True)
    if not exists_dir(path):
        return
    for root, _, files in os.walk(path, topdown=True):
        files.sort(key=lambda name: name.lower())
        for f in files:
            fpath = os.path.abspath(os.path.join(root, f))
            if has_file_ext(fpath, ext=ext):
                yield fpath if abs else os.path.relpath(fpath, path)
    return


def enum_dirs(path: str, abs: bool = False) -> Generator[str, None, None]:
    """\
    Enumerate all directories in the specified directory.
    Guarantees an alphabetical sorted order (case-insensitive) of directories.

    Args:
        path (str): The directory path to enumerate directories from.
        abs (bool, optional): If True, return absolute paths. Defaults to False.

    Yields:
        str: The directory path.
    """
    path = hpj(path, abs=True)
    if not exists_dir(path):
        return
    for root, dirs, _ in os.walk(path, topdown=True):
        dirs.sort(key=lambda name: name.lower())
        for d in dirs:
            dpath = os.path.abspath(os.path.join(root, d))
            yield dpath if abs else os.path.relpath(dpath, path)
    return


def enum_paths(
    path: str,
    ext: Union[None, str, List[str]] = None,
    abs: bool = False,
) -> Generator[str, None, None]:
    """\
    Enumerate all directories and files in the specified directory with optional extension filtering.
    Directories are always listed before files. Guarantees an alphabetical sorted order (case-insensitive) of files.

    Args:
        path (str): The directory path to enumerate paths from.
        ext (Union[str, List[str]]): The extension to check for. If `None`, return all files. If a string, checks for that specific extension. A string may contain multiple extensions separated by commas or semicolons, which will be split into a list. If a list, checks if the file has any of the extensions in the list. Each list item should be a string, which will check for that specific extension (preferably without a dot). Repeated extensions does NOT result in repeated files.
        abs (bool, optional): If True, return absolute paths. Defaults to False.

    Yields:
        str: The directory or file path.
    """
    path = hpj(path, abs=True)
    if not exists_dir(path):
        return
    for root, dirs, files in os.walk(path, topdown=True):
        dirs.sort(key=lambda name: name.lower())
        files.sort(key=lambda name: name.lower())
        for d in dirs:
            dpath = os.path.abspath(os.path.join(root, d))
            yield dpath if abs else os.path.relpath(dpath, path)
        for f in files:
            fpath = os.path.abspath(os.path.join(root, f))
            if has_file_ext(fpath, ext=ext):
                yield fpath if abs else os.path.relpath(fpath, path)


def empty_dir(path: str, ext: Union[None, str, List[str]] = None) -> bool:
    """\
    Check if a directory exists and is empty.
    If `ext` is provided, checks if there are any files with the specified extension(s) in the directory (recursively).

    Args:
        path (str): The directory path to check.
        ext (Union[str, List[str]]): The extension to check for. If `None`, return all files. If a string, checks for that specific extension. A string may contain multiple extensions separated by commas or semicolons, which will be split into a list. If a list, checks if the file has any of the extensions in the list. Each list item should be a string, which will check for that specific extension (preferably without a dot). Repeated extensions does NOT result in repeated files.

    Returns:
        bool: True if the directory exists and contains no items, False otherwise.
    """
    path = hpj(path, abs=True)
    if not exists_dir(path):
        return False
    try:
        next(enum_files(path, ext=ext))
        return False
    except StopIteration:
        return True


def nonempty_dir(path: str, ext: Union[None, str, List[str]] = None) -> bool:
    """\
    Check if a directory exists and is not empty.
    If `ext` is provided, checks if there are any files with the specified extension(s) in the directory (recursively).

    Args:
        path (str): The directory path to check.
        ext (Union[str, List[str]]): The extension to check for. If `None`, return all files. If a string, checks for that specific extension. A string may contain multiple extensions separated by commas or semicolons, which will be split into a list. If a list, checks if the file has any of the extensions in the list. Each list item should be a string, which will check for that specific extension (preferably without a dot). Repeated extensions does NOT result in repeated files.

    Returns:
        bool: True if the directory exists and contains at least one item, False otherwise.
    """
    path = hpj(path, abs=True)
    if not exists_dir(path):
        return False
    try:
        next(enum_files(path, ext=ext))
        return True
    except StopIteration:
        return False


def delete_file(path: str) -> bool:
    """\
    Delete a file at the specified path.

    Args:
        path (str): The file path to delete.

    Returns:
        bool: True if the file exists and was deleted, False otherwise.
    """
    path = hpj(path, abs=True)
    if exists_file(path):
        os.remove(path)
        return True
    return False


def delete_dir(path: str) -> bool:
    """\
    Delete a directory at the specified path.

    Args:
        path (str): The directory path to delete.

    Returns:
        bool: True if the directory exists and was deleted, False otherwise.
    """
    path = hpj(path, abs=True)
    if exists_dir(path):
        shutil.rmtree(path)
        return True
    return False


def delete_path(path: str) -> bool:
    """\
    Delete a path at the specified path.

    Args:
        path (str): The path to delete.

    Returns:
        bool: True if the path exists and was deleted, False otherwise.
    """
    path = hpj(path, abs=True)
    if exists_path(path):
        if os.path.isfile(path):
            return delete_file(path)
        if os.path.isdir(path):
            return delete_dir(path)
    return False


def copy_file(src: str, dst: str, mode: Literal["replace", "skip", "strict"] = "replace") -> str:
    """\
    Copy a file from source to destination.

    Args:
        src (str): The source file path.
        dst (str): The destination file path.
        mode (str, optional): The copy mode. 'replace' to overwrite, 'skip' to skip if exists, 'strict' to raise an error if exists. Defaults to 'replace'.

    Returns:
        str: The destination file path.

    Raises:
        ValueError: If the source does not exist or is not a file, or if the destination exists and mode is 'strict'.
    """
    src = hpj(src, abs=True)
    dst = hpj(dst, abs=True)
    if not exists_file(src):
        raise FileNotFoundError(f"Source file {src} does not exist or is not a file.")
    if exists_file(dst):
        if mode == "strict":
            raise FileExistsError(f"Destination file {dst} already exists. Use 'replace' or 'skip' copy mode to handle this.")
        if mode == "skip":
            return dst
    touch_file(dst)
    shutil.copy2(src, dst)
    return dst


def copy_dir(src: str, dst: str, mode: Literal["replace", "skip", "strict", "merge"] = "merge", **kwargs) -> str:
    """\
    Copy a directory from source to destination.

    Args:
        src (str): The source directory path.
        dst (str): The destination directory path.
        mode (str, optional): The copy mode. 'replace' to overwrite, 'skip' to skip if exists, 'strict' to raise an error if exists, 'merge' to merge contents. Defaults to 'merge'.
        **kwargs: Additional arguments to pass to shutil.copytree().

    Returns:
        str: The destination directory path.

    Raises:
        ValueError: If the source does not exist or is not a directory, or if the destination exists and mode is 'strict'.
    """
    src = hpj(src, abs=True)
    dst = hpj(dst, abs=True)
    if not exists_dir(src):
        raise FileNotFoundError(f"Source directory {src} does not exist or is not a directory.")
    if (mode == "replace") or (not exists_dir(dst)):
        touch_dir(dst, clear=True)
        shutil.copytree(src, dst, dirs_exist_ok=True, **kwargs)
        return dst
    if mode == "merge":
        shutil.copytree(src, dst, dirs_exist_ok=True, **kwargs)
        return dst
    if mode == "strict":
        conflicts = list()
        for f in enum_paths(src, abs=True):
            dstf = hpj(dst, os.path.relpath(f, src), abs=True)
            if exists_path(dstf):
                conflicts.append(dstf)
        if conflicts:
            raise FileExistsError(
                f"Destination directory {dst} already exists with conflicting files: {', '.join(conflicts)}. Use 'replace', 'skip', or 'merge' copy mode to handle this."
            )
        return
    for f in enum_paths(src, abs=True):
        dstf = hpj(dst, os.path.relpath(f, src), abs=True)
        if exists_path(dstf):
            if mode == "skip":
                continue
        shutil.copy2(f, dstf)
    return dst


def copy_path(src: str, dst: str, mode: Literal["replace", "skip", "strict", "merge"] = "merge", **kwargs) -> str:
    """\
    Copy a path from source to destination, handling both files and directories.

    Args:
        src (str): The source path.
        dst (str): The destination path.
        mode (str, optional): The copy mode. 'replace' to overwrite, 'skip' to skip if exists, 'strict' to raise an error if exists, 'merge' to merge contents. Defaults to 'merge'.
        **kwargs: Additional arguments to pass to shutil.copytree().

    Returns:
        str: The destination path.

    Raises:
        ValueError: If the source does not exist or is not a file/directory, or if the destination exists and mode is 'strict'.
    """
    src = hpj(src, abs=True)
    dst = hpj(dst, abs=True)
    if os.path.isfile(src):
        return copy_file(src, dst, mode=mode if mode != "merge" else "replace")
    if os.path.isdir(src):
        return copy_dir(src, dst, mode=mode, **kwargs)
    raise FileNotFoundError(f"Source path {src} does not exist or is not a file/directory.")


def folder_diagram(
    path: str,
    annotations: Optional[Dict[str, str]] = None,
    name: Optional[str] = None,
    limit: int = 16,
) -> str:
    """\
    Build a tree diagram from a directory path or serialized data.

    Creates a hierarchical tree structure showing the file/folder organization
    with optional annotations. This format is optimized for LLM understanding
    of the resource structure.

    Args:
        path (str): Directory path to build tree from.
        annotations (Optional[Dict[str, str]]): File-level annotations to display.
        name (Optional[str]): Custom label for the root node. Defaults to the basename of ``path``.
        limit (int, optional): Maximum number of entries to render per directory before collapsing the middle section.
            Defaults to 16, displaying at most 16 directories and 16 files per directory. It is recommended to set this to an even number.

    Returns:
        str: Formatted tree structure diagram with optional annotations.

    Example:
        >>> folder_diagram("/path/to/project", {"src/main.py": "Main entry point"})
        '''
        project/
        ├── file1.py
        └── src/
            └── main.py  # Main entry point
        '''
    """

    annotations = annotations or {}
    path = hpj(path, abs=True)
    bottom_limit = max(limit, 0) // 2
    top_limit = max(limit - bottom_limit, 0)

    root_label = name or get_file_basename(path)

    if not exists_path(path):
        raise ValueError(f"Path {path} is neither a file nor a directory.")

    if exists_file(path):
        # Single file case
        filename = get_file_basename(path)
        annotation_text = annotations.get(filename)
        annotation = f"  # {annotation_text}" if annotation_text else ""
        return f"{root_label}{annotation}"

    def build_recursive(current_path: str, current_prefix: str = "") -> List[str]:
        lines: List[str] = list()

        dirs = [{"path": d, "is_dir": True, "rel_root": os.path.relpath(d, path)} for d in list_dirs(current_path, abs=True)]
        files = [{"path": f, "is_dir": False, "rel_root": os.path.relpath(f, path)} for f in list_files(current_path, abs=True)]

        if len(dirs) > top_limit + bottom_limit + 1:
            dirs = dirs[:top_limit] + [{"omitted": len(dirs) - top_limit - bottom_limit}] + dirs[-bottom_limit:]
        if len(files) > top_limit + bottom_limit + 1:
            files = files[:top_limit] + [{"omitted": len(files) - top_limit - bottom_limit}] + files[-bottom_limit:]

        for index, entry in enumerate(dirs + files):
            is_last_child = index == len(dirs + files) - 1
            connector = "└── " if is_last_child else "├── "

            if "omitted" in entry:
                lines.append(f"{current_prefix}{connector}... (omitting {entry['omitted']} files)")
                continue

            child_path = entry["path"]
            is_directory = bool(entry["is_dir"])  # cast for typing clarity
            rel_root = entry["rel_root"]

            child_name = os.path.basename(child_path)
            item_label = f"{child_name}/" if is_directory else child_name

            annotation_key = annotations.get(rel_root) or annotations.get(child_name)
            annotation = f"  # {annotation_key}" if annotation_key else ""

            lines.append(f"{current_prefix}{connector}{item_label}{annotation}")

            if is_directory:
                next_prefix = current_prefix + ("    " if is_last_child else "│   ")
                lines.extend(build_recursive(child_path, next_prefix))

        return lines

    tree_lines = [f"{root_label}/"]
    tree_lines.extend(build_recursive(path))

    return "\n".join(tree_lines)
