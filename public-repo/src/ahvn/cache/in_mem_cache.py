"""\
In-memory cache backend.
"""

__all__ = [
    "InMemCache",
]

from .base import BaseCache

from typing import Any, Generator, Optional, Iterable, Dict


class InMemCache(BaseCache):
    """\
    An implementation of BaseCache that stores data in memory as Python dictionaries.
    """

    def __init__(self, exclude: Optional[Iterable[str]] = None, *args, **kwargs):
        """\
        Initialization.

        Args:
            exclude (Optional[Iterable[str]]): Keys to exclude from inputs when creating cache entries.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.
        """
        super().__init__(exclude=exclude, *args, **kwargs)
        self._cache: Dict[int, Any] = dict()

    def _has(self, key: int) -> bool:
        return key in self._cache

    def _get(self, key: int, default: Any = ...) -> Dict[str, Any]:
        return self._cache.get(key, default)

    def _set(self, key: int, value: Dict[str, Any]):
        self._cache[key] = value

    def _remove(self, key: int):
        if key in self._cache:
            del self._cache[key]

    def __len__(self) -> int:
        return len(self._cache)

    def _itervalues(self) -> Generator[Dict[str, Any], None, None]:
        yield from self._cache.values()
        return

    def _clear(self):
        self._cache.clear()

    def close(self):
        self._cache.clear()
        self._cache = None
