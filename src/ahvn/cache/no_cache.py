"""\
No-op cache implementation (always misses).
"""

__all__ = [
    "NoCache",
]

from .base import BaseCache

from typing import Any, Generator, Optional, Iterable, Dict


class NoCache(BaseCache):
    """\
    An implementation of BaseCache that does not cache any data.
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

    def _has(self, key: int) -> bool:
        return False

    def _get(self, key: int, default: Any = ...) -> Dict[str, Any]:
        return default

    def _set(self, key: int, value: Dict[str, Any]):
        pass

    def _remove(self, key: int):
        pass

    def __len__(self) -> int:
        return 0

    def _itervalues(self) -> Generator[Dict[str, Any], None, None]:
        return iter([])

    def _clear(self):
        pass
