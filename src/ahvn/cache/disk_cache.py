"""\
Disk-based cache powered by the 'diskcache' library.
"""

__all__ = [
    "DiskCache",
]

from ..utils.basic.config_utils import hpj
from ..utils.basic.file_utils import touch_dir
from .base import BaseCache

from diskcache import Cache
from typing import Any, Generator, Optional, Iterable, Dict


class DiskCache(BaseCache):
    """\
    An implementation of BaseCache that stores data on disk using diskcache.
    """

    def __init__(self, path: str, size_limit: int = int(32e9), exclude: Optional[Iterable[str]] = None, *args, **kwargs):
        """\
        Initialization.

        Args:
            path (str): Path to the directory where cache files will be stored.
            size_limit (int): Maximum size of the cache in bytes. Defaults to 32e9 (32 GB).
            exclude (Optional[Iterable[str]]): Keys to exclude from inputs when creating cache entries.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.
        """
        super().__init__(exclude=exclude, *args, **kwargs)
        self.path = hpj(path, abs=True)
        touch_dir(self.path)
        self._cache = Cache(directory=self.path, *args, **({"size_limit": size_limit} | kwargs))

    def _has(self, key: int) -> bool:
        return key in self._cache

    def _get(self, key: int, default: Any = ...) -> Dict[str, Any]:
        return self._cache.get(key, default)

    def _set(self, key: int, value: Dict[str, Any]):
        self._cache.set(key, value)

    def _remove(self, key: int):
        if key in self._cache:
            del self._cache[key]

    def __len__(self) -> int:
        return len(self._cache)

    def _itervalues(self) -> Generator[Dict[str, Any], None, None]:
        for key in self._cache:
            yield self._cache[key]

    def _clear(self):
        self._cache.clear()

    def close(self) -> None:
        """\
        Closes the cache.
        """
        self._cache.close()
        self._cache = None
