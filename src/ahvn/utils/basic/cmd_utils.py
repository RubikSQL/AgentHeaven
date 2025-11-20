__all__ = [
    "cmd",
    "is_macos",
    "is_windows",
    "is_linux",
    "browse",
]

from subprocess import Popen, PIPE
from typing import List, Dict, Any, Optional, Union, Literal
from .debug_utils import raise_mismatch


def cmd(
    command: Union[List[str], str],
    wait: bool = True,
    shell: bool = True,
    sudo: bool = False,
    include: Optional[Union[List[Literal["handle", "stdout", "stderr", "returncode"]], str]] = None,
    **kwargs,
) -> Union[Popen, str, Dict[str, Any]]:
    """\
    Run a command and return requested items.

    Args:
        command: command to run.
        wait: whether to wait for the process to finish.
        shell: pass to subprocess.Popen.
        sudo: prepend `sudo` to the command.
        include: list of keys to return. Default ["handle"].
            Supported keys: "handle" (the Popen object), "stdout", "stderr", "returncode".

    Return:
        If include == ["handle"] (default) returns the Popen object.
        If len(include) > 1 returns a dict mapping requested keys to values.
        If stdout/stderr are requested, they are captured via PIPE (unless provided in kwargs).
        If wait is False and stdout/stderr/returncode are requested, their values will be None
        (caller can read from process.stdout / process.stderr or wait later).
    """
    if include is None:
        include = ["handle"]
    if isinstance(include, str):
        include = [include]

    if isinstance(command, list):
        command = " ".join(command)
    command = f"sudo {command}" if sudo else f"{command}"

    # Validate requested include keys
    supported_includes = ["handle", "stdout", "stderr", "returncode"]
    for k in include:
        raise_mismatch(supported_includes, got=k, name="include")

    # Do not modify the caller-provided kwargs in-place. Work on a shallow copy.
    local_kwargs = dict(kwargs)

    # Default to text mode (return str instead of bytes) unless caller specified otherwise
    if "text" not in local_kwargs and "universal_newlines" not in local_kwargs and "encoding" not in local_kwargs:
        local_kwargs["text"] = True

    want_stdout = "stdout" in include
    want_stderr = "stderr" in include

    # Ensure pipes if stdout/stderr requested and not already provided
    if want_stdout and "stdout" not in local_kwargs:
        local_kwargs["stdout"] = PIPE
    if want_stderr and "stderr" not in local_kwargs:
        local_kwargs["stderr"] = PIPE

    process = Popen(command, shell=shell, **local_kwargs)

    # If only handle requested, return it immediately (respect wait=True semantics by waiting first)
    if include == ["handle"]:
        if wait:
            process.wait()
        return process

    # Need to gather outputs if waiting and capturing was requested
    if wait:
        if want_stdout or want_stderr:
            out, err = process.communicate()
        else:
            process.wait()
            out, err = None, None

        result: Dict[str, Any] = {}
        for key in include:
            if key == "handle":
                result["handle"] = process
            elif key == "stdout":
                result["stdout"] = None if out is None else out.strip()
            elif key == "stderr":
                result["stderr"] = None if err is None else err.strip()
            elif key == "returncode":
                result["returncode"] = process.returncode
            else:
                result[key] = None
        if len(result) == 1:
            return next(iter(result.values()))
        return result

    # wait == False and include requested multiple items: return handle plus PIPE/objects
    result = {}
    for key in include:
        if key == "handle":
            result["handle"] = process
        elif key == "stdout":
            # return the stdout object (None if not captured, file-like if PIPE)
            result["stdout"] = process.stdout
        elif key == "stderr":
            result["stderr"] = process.stderr
        elif key == "returncode":
            result["returncode"] = None
        else:
            result[key] = None

    if len(result) == 1:
        return next(iter(result.values()))
    return result


import platform


def is_macos() -> bool:
    """\
    Return whether the current platform is macOS.
    """
    return platform.system() == "Darwin"


def is_windows() -> bool:
    """\
    Return whether the current platform is Windows.
    """
    return platform.system() == "Windows"


def is_linux() -> bool:
    """\
    Return whether the current platform is Linux.
    """
    return platform.system() == "Linux"


def browse(path: str):
    """\
    Open the file with a text editor, or open the folder in the file explorer. Platform-agnostic.

    Args:
        path (str): The path to the file or folder to open.
    """
    import os

    if is_macos():
        Popen(["open", path])
    elif is_windows():
        # Use startfile for files/folders on Windows
        os.startfile(path)
    elif is_linux():
        Popen(["xdg-open", path])
    else:
        # Fallback to open (macOS default)
        Popen(["open", path])
