__all__ = [
    "Progress",
    "NoProgress",
    "LogProgress",
    "TqdmProgress",
    "get_progress",
    "progress",
]

from abc import ABC, abstractmethod
from contextlib import contextmanager
from threading import local, Lock
from typing import Optional, List, Any, Dict
import logging

from .log_utils import get_logger


class Progress(ABC):
    """\
    Abstract base class for progress reporting.

    Provides a unified interface for progress tracking that can be extended
    for different backends (tqdm, custom frontends, etc.).

    Subclasses must implement: emit, update_total, update, close.
    Optional helpers: set_description, set_postfix, write.
    """

    def __init__(
        self,
        total: Optional[int] = None,
        desc: Optional[str] = None,
        initial: int = 0,
        unit: str = "it",
        leave: bool = True,
    ):
        """\
        Initialize the progress bar.

        Args:
            total (Optional[int]): Total number of iterations. None for unknown.
            desc (Optional[str]): Description prefix for the progress bar.
            initial (int): Initial counter value.
            unit (str): Unit of iteration.
            leave (bool): Whether to leave the progress bar after completion.
        """
        self._total = total
        self._desc = desc
        self._n = initial
        self._unit = unit
        self._leave = leave
        self._closed = False

    @property
    def total(self) -> Optional[int]:
        """Get total iterations."""
        return self._total

    @total.setter
    def total(self, value: Optional[int]):
        """Set total iterations."""
        self._total = value
        self._on_total_change()

    @property
    def n(self) -> int:
        """Get current iteration count."""
        return self._n

    @property
    def desc(self) -> Optional[str]:
        """Get description."""
        return self._desc

    def _on_total_change(self):
        """Hook called when total changes. Override in subclasses if needed."""
        pass

    def emit(self, payload: Optional[Dict[str, Any]]) -> Optional[Any]:
        """\
        Emit a structured progress update.

        The base implementation maps standardized keys:
        - `total`: calls update_total
        - `update`/`advance`: calls update
        - `refresh`: forwarded to subclasses when they override emit

        Args:
            payload (Optional[Dict[str, Any]]): Progress payload to interpret.

        Returns:
            Optional[Any]: Subclass-specific return value.
        """
        if payload is None:
            return None

        if "total" in payload:
            self.update_total(payload.get("total"))

        if "update" in payload or "advance" in payload:
            amount = payload.get("update")
            if amount is None:
                amount = payload.get("advance")
            amount = 0 if amount is None else amount
            self.update(int(amount))

        return None

    def write(self, s: str, level: int = logging.INFO, **kwargs) -> None:
        """\
        Write a message through the progress bar's output mechanism.
        Default to using the AgentHeaven logger using the progress bar's class name.

        Args:
            s (str): The string to write.
            level (int): Logging level to use. Defaults to logging.INFO.
            **kwargs: Additional keyword arguments for logging.
        """
        logger = get_logger(self.__class__.__name__)
        logger.log(level=level, msg=str(s).strip(), **kwargs)

    @abstractmethod
    def update_total(self, total: Optional[int]) -> None:
        """\
        Update the total iterations for the progress bar.

        Args:
            total (Optional[int]): New total iterations; None for unknown.
        """
        pass

    @abstractmethod
    def update(self, n: int = 1) -> None:
        """\
        Update the progress bar by n steps.

        Args:
            n (int): Number of steps to advance.
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Close and cleanup the progress bar."""
        pass

    def reset(self, total: Optional[int] = None) -> None:
        """\
        Reset the progress bar to initial state.

        Args:
            total (Optional[int]): New total, or keep existing if None.
        """
        self._n = 0
        if total is not None:
            self.total = total

    def __enter__(self) -> "Progress":
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager and close progress bar."""
        self.close()


class NoProgress(Progress):
    """\
    A silent progress implementation that does nothing.

    Used as the default when no progress bar is requested.
    """

    def update(self, n: int = 1) -> None:
        self._n += n

    def emit(self, payload: Optional[Dict[str, Any]]) -> Optional[Any]:
        return super().emit(payload)

    def update_total(self, total: Optional[int]) -> None:
        self.total = total

    def set_description(self, desc: Optional[str] = None, refresh: bool = True) -> None:
        self._desc = desc

    def set_postfix(self, ordered_dict: Optional[dict] = None, refresh: bool = True, **kwargs) -> None:
        pass

    def close(self) -> None:
        self._closed = True


class LogProgress(Progress):
    """\
    Progress implementation using logging.

    Outputs progress as log messages in format: [INFO] <desc>: <prefix> [xx%] <suffix>
    Logs at configurable intervals to avoid spam.
    """

    def __init__(
        self,
        total: Optional[int] = None,
        desc: Optional[str] = None,
        initial: int = 0,
        unit: str = "it",
        leave: bool = True,
        logger: Optional[logging.Logger] = None,
        level: int = logging.INFO,
        interval: int = 10,
    ):
        """\
        Initialize logger-based progress.

        Args:
            total (Optional[int]): Total number of iterations.
            desc (Optional[str]): Description prefix.
            initial (int): Initial counter value.
            unit (str): Unit of iteration.
            leave (bool): Whether to log completion message.
            logger (Optional[logging.Logger]): Logger to use. Defaults to ahvn logger.
            level (int): Log level. Defaults to INFO.
            interval (int): Log every N percent change. Defaults to 10.
        """
        super().__init__(total=total, desc=desc, initial=initial, unit=unit, leave=leave)
        self._logger = logger or get_logger(__name__)
        self._level = level
        self._interval = interval
        self._last_logged_pct = -interval
        self._prefix = ""
        self._suffix = ""

    def _format_message(self) -> str:
        """Format the progress message."""
        parts = []
        if self._desc:
            parts.append(self._desc)
        if self._prefix:
            parts.append(self._prefix)
        if self._total and self._total > 0:
            pct = int(100 * self._n / self._total)
            parts.append(f"[{pct}%]")
        else:
            parts.append(f"[{self._n} {self._unit}]")
        if self._suffix:
            parts.append(self._suffix)
        return ": ".join(parts) if parts else ""

    def _should_log(self) -> bool:
        """Check if we should log based on interval."""
        if not self._total or self._total <= 0:
            return True
        pct = int(100 * self._n / self._total)
        if pct >= self._last_logged_pct + self._interval:
            self._last_logged_pct = pct
            return True
        return False

    def emit(self, payload: Optional[Dict[str, Any]]) -> Optional[Any]:
        super().emit(payload)
        if payload and ("message" in payload or "status" in payload):
            self._logger.log(self._level, str(payload))
        return None

    def update_total(self, total: Optional[int]) -> None:
        self.total = total
        self._last_logged_pct = -self._interval

    def update(self, n: int = 1) -> None:
        self._n += n
        if self._should_log():
            self._logger.log(self._level, self._format_message())

    def set_description(self, desc: Optional[str] = None, refresh: bool = True) -> None:
        self._desc = desc

    def set_postfix(self, ordered_dict: Optional[dict] = None, refresh: bool = True, **kwargs) -> None:
        postfix = ordered_dict or {}
        postfix.update(kwargs)
        self._suffix = ", ".join(f"{k}={v}" for k, v in postfix.items())

    def set_prefix(self, prefix: str) -> None:
        """Set prefix text (between description and percentage)."""
        self._prefix = prefix

    def write(self, s: str, level: Optional[int] = None, **kwargs) -> None:
        """\
        Write a message through the progress bar's logging mechanism.

        Args:
            s (str): The string to write.
            level (Optional[int]): Logging level to use. Defaults to the progress bar's level.
            **kwargs: Additional keyword arguments for logging.
        """
        log_level = level if level is not None else self._level
        self._logger.log(level=log_level, msg=str(s).strip(), **kwargs)

    def close(self) -> None:
        if not self._closed:
            if self._leave and self._total and self._n >= self._total:
                self._logger.log(self._level, self._format_message())
            self._closed = True


class TqdmProgress(Progress):
    """\
    Progress implementation using tqdm.

    Wraps tqdm to provide a consistent interface with other Progress implementations.
    """

    def __init__(
        self,
        total: Optional[int] = None,
        desc: Optional[str] = None,
        initial: int = 0,
        unit: str = "it",
        leave: bool = True,
        **tqdm_kwargs,
    ):
        """\
        Initialize tqdm-based progress bar.

        Args:
            total (Optional[int]): Total number of iterations.
            desc (Optional[str]): Description prefix.
            initial (int): Initial counter value.
            unit (str): Unit of iteration.
            leave (bool): Whether to leave progress bar after completion.
            **tqdm_kwargs: Additional arguments passed to tqdm.
        """
        super().__init__(total=total, desc=desc, initial=initial, unit=unit, leave=leave)
        import tqdm as tqdm_module

        self._tqdm = tqdm_module.tqdm(
            total=total,
            desc=desc,
            initial=initial,
            unit=unit,
            leave=leave,
            **tqdm_kwargs,
        )

    def _on_total_change(self):
        """Update tqdm's total when our total changes."""
        if hasattr(self, "_tqdm") and self._tqdm is not None:
            self._tqdm.total = self._total
            self._tqdm.refresh()

    def update_total(self, total: Optional[int]) -> None:
        self.total = total

    def update(self, n: int = 1) -> None:
        self._n += n
        self._tqdm.update(n)

    def emit(self, payload: Optional[Dict[str, Any]]) -> Optional[Any]:
        if payload:
            desc = payload.get("description")
            if desc is not None:
                self.set_description(desc, refresh=payload.get("refresh", True))

            postfix_dict = payload.get("postfix_dict")
            if postfix_dict is None and "postfix" in payload:
                postfix = payload.get("postfix")
                if isinstance(postfix, dict):
                    postfix_dict = postfix
                elif postfix is not None:
                    postfix_dict = {"postfix": postfix}
            if postfix_dict is not None:
                self.set_postfix(postfix_dict, refresh=payload.get("refresh", True))

        return super().emit(payload)

    def set_description(self, desc: Optional[str] = None, refresh: bool = True) -> None:
        self._desc = desc
        self._tqdm.set_description(desc, refresh=refresh)

    def set_postfix(self, ordered_dict: Optional[dict] = None, refresh: bool = True, **kwargs) -> None:
        self._tqdm.set_postfix(ordered_dict, refresh=refresh, **kwargs)

    def write(self, s: str, file: Any = None, end: str = "\n", **kwargs) -> None:
        """\
        Write a message through the tqdm progress bar's output mechanism.

        Args:
            s (str): The string to write.
            file (Any): File-like object to write to. Defaults to sys.stderr.
            end (str): End character. Defaults to newline.
            **kwargs: Additional keyword arguments for logging.
        """
        self._tqdm.write(s, file=file, end=end, **kwargs)

    def close(self) -> None:
        if not self._closed:
            self._tqdm.close()
            self._closed = True

    def reset(self, total: Optional[int] = None) -> None:
        super().reset(total)
        self._tqdm.reset(total)

    @property
    def pbar(self) -> Any:
        """Access the underlying tqdm progress bar for advanced operations."""
        return self._tqdm


# Thread-local storage for progress context stack
_thread_local = local()
_init_lock = Lock()


def _get_stack() -> List[Progress]:
    """Get the progress stack for the current thread, initializing if needed."""
    if not hasattr(_thread_local, "progress_stack"):
        with _init_lock:
            if not hasattr(_thread_local, "progress_stack"):
                _thread_local.progress_stack = []
    return _thread_local.progress_stack


def get_progress() -> Progress:
    """\
    Get the currently active progress bar for this thread.

    Returns:
        Progress: The active progress bar, or a NoProgress instance if none is active.
    """
    stack = _get_stack()
    if stack:
        return stack[-1]
    return NoProgress()


@contextmanager
def progress(p: Progress):
    """\
    Context manager to set the active progress bar.

    Supports nesting - each context pushes onto a stack and pops on exit.

    Args:
        p (Progress): The progress bar to activate.

    Yields:
        Progress: The activated progress bar.

    Example:
        with progress(TqdmProgress(total=100)) as pbar:
            for i in range(100):
                pbar.update(1)
    """
    stack = _get_stack()
    stack.append(p)
    try:
        yield p
    finally:
        stack.pop()
        if not p._closed:
            p.close()
