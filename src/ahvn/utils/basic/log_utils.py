__all__ = [
    "get_logger",
]

from .color_utils import *

from typing import Callable, Dict, Any, Optional, Union
import logging
import os

_SUCCESS_LEVEL_NO = 25
logging.addLevelName(_SUCCESS_LEVEL_NO, "SUCCESS")


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
        level_str = level
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
