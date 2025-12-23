__all__ = [
    "CacheKLStore",
]


from .base import BaseKLStore
from ..cache.base import BaseCache
from ..ukf.base import BaseUKF
from typing import Any, Generator, Optional, Callable


class CacheKLStore(BaseKLStore):
    """\
    KLStore implementation backed by a BaseCache instance.
    Stores BaseUKF objects in the cache, using kl.id as the key.

    Args:
        cache (BaseCache): The cache backend to use for storing BaseUKF objects.
    """

    def __init__(self, cache: BaseCache, name: Optional[str] = None, condition: Optional[Callable] = None, *args, **kwargs):
        """\
        Initialize CacheKLStore with a BaseCache instance.

        Args:
            cache (BaseCache): The cache backend to use.
            name: Name of the KLStore instance. If None, defaults to "default".
            condition: Optional upsert/insert condition to apply to the KLStore.
                KLs that do not satisfy the condition will be ignored. If None, all KLs are accepted.
            *args: Additional positional arguments for BaseKLStore.
            **kwargs: Additional keyword arguments for BaseKLStore.
        """
        super().__init__(name=name, condition=condition, *args, **kwargs)
        self.cache = cache

    def _has(self, key: int) -> bool:
        """\
        Check if a KL with the given key exists in the cache.

        Args:
            key (int): The KL id to check.

        Returns:
            bool: True if exists, False otherwise.
        """
        return self.cache.exists(func="kl_store", kid=key)

    def _get(self, key: int, default: Any = ...) -> Optional[BaseUKF]:
        """\
        Retrieve a KL (BaseUKF) by its key from the store.

        Args:
            key (int): The KL id to retrieve.
            default (Any): The default value to return if not found.

        Returns:
            BaseUKF or default: The retrieved KL instance if found, otherwise default.
        """
        result = self.cache.get(func="kl_store", kid=key)
        return default if result is ... else BaseUKF.from_dict(result, polymorphic=True)

    def _upsert(self, kl: BaseUKF, **kwargs):
        """\
        Insert or update a KL in the store.

        Args:
            kl (BaseUKF): The KL to upsert.
            **kwargs: Additional keyword arguments.
        """
        self.cache.set(func="kl_store", output=kl.to_dict(), kid=kl.id)

    def _remove(self, key: int, **kwargs):
        """\
        Remove a KL from the store by its key.

        Args:
            key (int): The KL id to remove.
            **kwargs: Additional keyword arguments.
        """
        self.cache.unset(func="kl_store", kid=key)

    def __len__(self) -> int:
        return len(self.cache)

    def _itervalues(self) -> Generator[BaseUKF, None, None]:
        """\
        Return an iterator over all KLs in the store.

        Yields:
            BaseUKF: Each KL stored in the store.
        """
        for entry in self.cache:
            if entry.func == "kl_store":
                yield BaseUKF.from_dict(entry.output, polymorphic=True)

    def _clear(self):
        """\
        Clear all KLs from the store.
        """
        self.cache.clear()

    def close(self):
        """\
        Close the cache of the store.
        """
        self.cache.close()
        self.cache = None

    def flush(self, **kwargs):
        """\
        Flush the cache of the store.
        """
        self.cache.flush(**kwargs)
