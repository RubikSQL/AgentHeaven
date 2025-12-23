__all__ = [
    "get_logger",
    "set_log_level",
    "redirect_logs",
    "restore_logs",
    "SuppressOutput",
]

from .color_utils import *

from typing import Callable, Dict, Any, Optional, Union, List
import logging
import os
import sys

_SUCCESS_LEVEL_NO = 25
logging.addLevelName(_SUCCESS_LEVEL_NO, "SUCCESS")

# Store original handlers for restoration
_original_handlers: Dict[str, List[logging.Handler]] = {}


def set_log_level(
    level: Union[str, int],
    loggers: Optional[List[str]] = None,
) -> None:
    """\
    Set the log level globally for ahvn and optionally other loggers.

    Args:
        level (Union[str, int]): The log level (e.g., "DEBUG", "INFO", "WARNING", logging.WARNING).
        loggers (Optional[List[str]]): List of logger names to configure.
            If None, configures "ahvn" logger and root logger.

    Example:
        >>> set_log_level("WARNING")  # Suppress INFO/DEBUG messages
        >>> set_log_level(logging.DEBUG, ["ahvn", "myapp"])  # Enable debug for specific loggers
    """
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    target_loggers = loggers if loggers is not None else ["ahvn"]

    for logger_name in target_loggers:
        logging.getLogger(logger_name).setLevel(level)

    # Also set root logger if no specific loggers provided
    if loggers is None:
        root = logging.getLogger()
        if not root.handlers:
            root.setLevel(level)


def redirect_logs(
    filepath: str,
    loggers: Optional[List[str]] = None,
    level: Optional[Union[str, int]] = None,
    fmt: Optional[str] = None,
) -> None:
    """\
    Redirect ahvn logging output to a file.

    Args:
        filepath (str): Path to the log file.
        loggers (Optional[List[str]]): List of logger names to redirect.
            If None, redirects "ahvn" logger.
        level (Optional[Union[str, int]]): Log level for the file handler.
            If None, uses the current logger level.
        fmt (Optional[str]): Log message format.

    Example:
        >>> redirect_logs("/tmp/ahvn.log")
        >>> redirect_logs("/tmp/debug.log", level="DEBUG", loggers=["ahvn", "myapp"])
    """
    target_loggers = loggers if loggers is not None else ["ahvn"]

    # Create file handler
    file_handler = logging.FileHandler(filepath, mode="a", encoding="utf-8")
    if fmt:
        file_handler.setFormatter(logging.Formatter(fmt))
    else:
        file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

    if level is not None:
        if isinstance(level, str):
            level = getattr(logging, level.upper(), logging.INFO)
        file_handler.setLevel(level)

    for logger_name in target_loggers:
        logger = logging.getLogger(logger_name)

        # Store original handlers if not already stored
        if logger_name not in _original_handlers:
            _original_handlers[logger_name] = list(logger.handlers)

        # Remove existing stream handlers (keep file handlers)
        for handler in logger.handlers[:]:
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                logger.removeHandler(handler)

        # Add file handler
        logger.addHandler(file_handler)


def restore_logs(loggers: Optional[List[str]] = None) -> None:
    """\
    Restore original log handlers for specified loggers.

    Args:
        loggers (Optional[List[str]]): List of logger names to restore.
            If None, restores all loggers that were modified.

    Example:
        >>> restore_logs()  # Restore all modified loggers
        >>> restore_logs(["ahvn"])  # Restore specific logger
    """
    target_loggers = loggers if loggers is not None else list(_original_handlers.keys())

    for logger_name in target_loggers:
        if logger_name in _original_handlers:
            logger = logging.getLogger(logger_name)

            # Remove all current handlers
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)

            # Restore original handlers
            for handler in _original_handlers[logger_name]:
                logger.addHandler(handler)

            del _original_handlers[logger_name]


class SuppressOutput:
    """\
    Context manager to suppress stdout/stderr at the OS file descriptor level.

    This is more aggressive than redirecting sys.stdout/sys.stderr and can
    capture output from C libraries and subprocesses as well.

    Use `restore()` and `suppress()` methods for temporary restoration during
    the suppression context (e.g., for updating progress displays).

    Attributes:
        suppress_stdout (bool): Whether to suppress stdout.
        suppress_stderr (bool): Whether to suppress stderr.

    Example:
        >>> with SuppressOutput():
        ...     # All output suppressed here
        ...     noisy_library_call()

        >>> with SuppressOutput(suppress_stderr=False):
        ...     # Only stdout suppressed, stderr still visible
        ...     pass

        >>> with SuppressOutput() as suppressor:
        ...     noisy_setup()
        ...     suppressor.restore()  # Temporarily show output
        ...     print("Progress update")
        ...     suppressor.suppress()  # Continue suppressing
        ...     more_noisy_code()
    """

    def __init__(self, suppress_stdout: bool = True, suppress_stderr: bool = True):
        """\
        Initialize the SuppressOutput context manager.

        Args:
            suppress_stdout (bool): Whether to suppress stdout. Defaults to True.
            suppress_stderr (bool): Whether to suppress stderr. Defaults to True.
        """
        self.suppress_stdout = suppress_stdout
        self.suppress_stderr = suppress_stderr
        self._devnull = None
        self._old_stdout_fd = None
        self._old_stderr_fd = None
        self._suppressing = False

    def __enter__(self) -> "SuppressOutput":
        # Open devnull
        self._devnull = open(os.devnull, "w")

        # Save original file descriptors
        if self.suppress_stdout:
            self._old_stdout_fd = os.dup(sys.stdout.fileno())
        if self.suppress_stderr:
            self._old_stderr_fd = os.dup(sys.stderr.fileno())

        # Start suppressed
        self.suppress()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore original stdout/stderr
        self.restore()

        if self._old_stdout_fd is not None:
            os.close(self._old_stdout_fd)
            self._old_stdout_fd = None
        if self._old_stderr_fd is not None:
            os.close(self._old_stderr_fd)
            self._old_stderr_fd = None
        if self._devnull is not None:
            self._devnull.close()
            self._devnull = None

        return False

    def suppress(self) -> None:
        """\
        Redirect stdout/stderr to devnull.
        """
        if self._suppressing or self._devnull is None:
            return
        if self.suppress_stdout and self._old_stdout_fd is not None:
            os.dup2(self._devnull.fileno(), sys.stdout.fileno())
        if self.suppress_stderr and self._old_stderr_fd is not None:
            os.dup2(self._devnull.fileno(), sys.stderr.fileno())
        self._suppressing = True

    def restore(self) -> None:
        """\
        Restore original stdout/stderr temporarily.
        """
        if not self._suppressing:
            return
        if self.suppress_stdout and self._old_stdout_fd is not None:
            os.dup2(self._old_stdout_fd, sys.stdout.fileno())
        if self.suppress_stderr and self._old_stderr_fd is not None:
            os.dup2(self._old_stderr_fd, sys.stderr.fileno())
        self._suppressing = False


class ColoredFormatter(logging.Formatter):
    """\
    Custom formatter to add color to log messages.

    Attributes:
        colors (dict[int, Callable[[Any, bool], str]]): Mapping of log levels to color functions.
    """

    colors = {
        logging.NOTSET: no_color,  # 0
        logging.DEBUG: color_debug,  # 10
        logging.INFO: color_info,  # 20
        _SUCCESS_LEVEL_NO: color_success,  # 25
        logging.WARNING: color_warning,  # 30
        logging.ERROR: color_error,  # 40
        logging.CRITICAL: color_error,  # 50
    }

    def __init__(
        self,
        fmt: Optional[str] = None,
        datefmt: Optional[str] = None,
        style: str = "%",
        *,
        validate: bool = True,
        colors: Optional[Dict[int, Callable[[Any, bool], str]]] = None,
    ):
        """\
        Initialize the ColoredFormatter.

        Args:
            fmt (Optional[str]): Log message format.
            datefmt (Optional[str]): Date format.
            style (str): Format style.
            validate (bool): Whether to validate the format.
            colors (Optional[dict[int, Callable[[Any, bool], str]]]): Custom color functions.
        """
        super().__init__(fmt, datefmt, style, validate=validate)
        if colors is not None:
            self.colors.update(colors)

    def format(self, record: logging.LogRecord) -> str:
        """\
        Format the log record with color.

        Args:
            record (logging.LogRecord): The log record to format.

        Returns:
            str: The formatted log message with color.
        """
        message = super().format(record)
        coloring_func = getattr(record, "color", self.colors.get(record.levelno, no_color))
        return coloring_func(message, console=True)


def get_logger(
    name: str,
    level: Optional[Union[str, int]] = None,
    fmt: Optional[str] = None,
    datefmt: Optional[str] = None,
    style: str = "%",
    *,
    validate: bool = True,
    colors: Optional[Dict[int, Callable[[Any, bool], str]]] = None,
) -> logging.Logger:
    """\
    Get a logger with a custom colored formatter.

    Args:
        name (str): The name of the logger.
        level (Optional[Union[str, int]]): The default log level.
        fmt (Optional[str]): The log message format.
        datefmt (Optional[str]): The date format.
        colors (Optional[dict[int, Callable[[Any, bool], str]]]): Custom color functions for log levels.

    Returns:
        logging.Logger: The configured logger.
    """
    logger = logging.getLogger(name)
    if level is None:
        level = os.environ.get("LOG_LEVEL")
    if isinstance(level, int):
        level_str = logging.getLevelName(level)
    else:
        level_str = level.upper() if level is not None else None
    logger.setLevel(level_str or logging.INFO)

    def success(self, message: Any, *args: Any, **kwargs: Any):
        """\
        Log a message with level `SUCCESS`.

        Args:
            message (Any): The log message.
            *args: Additional arguments.
            **kwargs: Additional keyword arguments.
        """
        if self.isEnabledFor(_SUCCESS_LEVEL_NO):
            self._log(_SUCCESS_LEVEL_NO, message, args, **kwargs)

    if not hasattr(logger, "success"):
        logger.success = success.__get__(logger, logging.Logger)

    # Skip method wrapping to avoid recursion issues
    # The colored formatting will be handled by the ColoredFormatter instead

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(ColoredFormatter(fmt, datefmt, style=style, validate=validate, colors=colors))
        logger.addHandler(handler)
        logger.propagate = False  # Prevent propagation to the root logger

    return logger
