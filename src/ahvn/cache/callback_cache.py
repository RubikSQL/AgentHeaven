"""\
Callback-based cache implementation (no storage, only triggers callbacks on set).
"""

__all__ = [
    "CallbackCache",
]

from ..utils.basic.log_utils import get_logger

logger = get_logger(__name__)

from .base import BaseCache
from typing import Any, Generator, Optional, Iterable, Dict, Callable, Union


class CallbackCache(BaseCache):
    """\
    An implementation of BaseCache that does not cache any data, but calls callbacks on set, and feeds on get.
    """

    def __init__(
        self,
        callbacks: Optional[Iterable[Callable[[int, Dict[str, Any]], None]]] = None,
        feeds: Optional[Iterable[Callable[[Callable, Any], None]]] = None,
        exclude: Optional[Iterable[str]] = None,
        *args,
        **kwargs,
    ):
        """\
        Initialization.

        Args:
            callbacks (Optional[Iterable[Callable[[int, Dict[str, Any]], None]]]): List of callback functions to call on set.
                Each callback function must has API `callback(key: int, value: Dict[str, Any])`, which handles a cache set event.
            feeds (Optional[Iterable[Callable[[Union[Callable, str], Any], None]]]): List of feed functions to call on get.
                Each feed function must have API `feed(func: Union[Callable, str], **kwargs)`, which handles a cache get event.
                The kwargs are the input to the function.
                Notice that feeds must be ordered: the first feed function with a non-Ellipsis return value will be used.
            exclude (Optional[Iterable[str]]): Keys to exclude from inputs when creating cache entries.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.
        """
        super().__init__(exclude=exclude, *args, **kwargs)
        self.callbacks = callbacks or list()
        self.feeds = feeds or list()

    def _has(self, key: int) -> bool:
        raise NotImplementedError("CallbackCache does not support `_has`.")

    def _get(self, key: int, default: Any = ...) -> Dict[str, Any]:
        raise NotImplementedError("CallbackCache does not support `_get`.")

    def _set(self, key: int, value: Dict[str, Any]):
        for cb in self.callbacks:
            try:
                cb(key, value)
            except Exception as e:
                logger.error(f"Error occurred in callback for key {key}: {e}. Skipped.")
                pass  # Ignore callback errors

    def _remove(self, key: int):
        raise NotImplementedError("CallbackCache does not support `_remove`.")

    def __len__(self) -> int:
        return 0

    def _itervalues(self) -> Generator[Dict[str, Any], None, None]:
        return iter([])

    def _clear(self):
        raise NotImplementedError("CallbackCache does not support `_clear`.")

    def get(self, func: Union[Callable, str], **kwargs) -> Any:
        """\
        Retrieves a cached value for the given function and inputs.

        Args:
            func (Union[Callable, str]): The function or its name to retrieve the cached value for.
                Notice that for `CallbackCache`, when all feed functions return ..., the function will be called:
                # (deprecated) If the `func` is callable, it will be called with the provided keyword arguments.
                # (deprecated) Otherwise, it will NOT be called.
                For better stability, it is recommend to use a default feed function that can handle missing values.
            **kwargs: Arbitrary keyword arguments representing the inputs to the function.

        Returns:
            Any: The cached output if found, otherwise `Ellipsis` (to avoid collisions with functions returning None).
        """
        for fd in self.feeds:
            try:
                result = fd(func, **kwargs)
            except Exception as e:
                logger.error(f"Error occurred in feed for function {func}: {e}. Skipped.")
                result = ...
            if result is not ...:
                return result
        # if callable(func):
        #     result = func(**kwargs)
        #     return result
        return ...
