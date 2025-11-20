__all__ = [
    "CascadeKLStore",
]


from .base import BaseKLStore
from ..ukf.base import BaseUKF
from typing import Any, Generator, Optional, List, Callable


class CascadeKLStore(BaseKLStore):
    """\
    KLStore implementation that cascades through an ordered list of KLStores.

    For get/has operations: tries each store in order until found.
    For remove/clear operations: operates on all stores.
    For upsert operations: raises an error, requiring upsert to individual stores.
    For iteration: returns deduplicated results from all stores.

    Args:
        stores (List[BaseKLStore]): Ordered list of KLStores to cascade through.
    """

    def __init__(self, stores: List[BaseKLStore] = None, name: Optional[str] = None, condition: Optional[Callable] = None, *args, **kwargs):
        """\
        Initialize CascadeKLStore with a list of stores.

        Args:
            stores (List[BaseKLStore]): Ordered list of KLStores.
            name: Name of the KLStore instance. If None, defaults to "default".
            condition: Optional upsert/insert condition to apply to the KLStore.
                KLs that do not satisfy the condition will be ignored. If None, all KLs are accepted.
            *args: Additional positional arguments for BaseKLStore.
            **kwargs: Additional keyword arguments for BaseKLStore.
        """
        super().__init__(name=name, condition=condition, *args, **kwargs)
        self.storages = stores or list()

    def _has(self, key: int) -> bool:
        """\
        Check if a KL with the given key exists in any of the stores.

        Args:
            key (int): The KL id to check.

        Returns:
            bool: True if exists in any store, False otherwise.
        """
        for store in self.storages:
            if store._has(key):
                return True
        return False

    def _get(self, key: int, default: Any = ...) -> Optional[BaseUKF]:
        """\
        Retrieve a KL (BaseUKF) by its key from the first store that has it.

        Args:
            key (int): The KL id to retrieve.
            default (Any): The default value to return if not found.

        Returns:
            BaseUKF or default: The retrieved KL instance if found, otherwise default.
        """
        for store in self.storages:
            result = store._get(key, default=...)
            if result is not ...:
                return result
        return default

    def _upsert(self, kl: BaseUKF, **kwargs):
        """\
        Upsert operation is not allowed in CascadeKLStore.
        Users should upsert directly into specific stores.

        Args:
            kl (BaseUKF): The KL to upsert.
            **kwargs: Additional keyword arguments.

        Raises:
            NotImplementedError: Always raised to prevent direct upsert.
        """
        raise NotImplementedError("Upsert operation is not allowed in `CascadeKLStore`." "Please upsert directly into the specific store you want to modify.")

    def _remove(self, key: int, **kwargs):
        """\
        Remove a KL from all stores that contain it.

        Args:
            key (int): The KL id to remove.
            **kwargs: Additional keyword arguments.
        """
        for store in self.storages:
            if store._has(key):
                store._remove(key, **kwargs)

    def __len__(self) -> int:
        """\
        Return the number of unique KLs across all stores.

        Returns:
            int: Number of unique KLs.
        """
        return len(list(self._itervalues()))

    def _itervalues(self) -> Generator[BaseUKF, None, None]:
        """\
        Return an iterator over all unique KLs from all stores.
        Deduplicates based on KL id, yielding the first occurrence found.

        Yields:
            BaseUKF: Each unique KL stored across all stores.
        """
        seen_ids = set()
        for store in self.storages:
            for kl in store._itervalues():
                if kl.id not in seen_ids:
                    seen_ids.add(kl.id)
                    yield kl

    def _clear(self):
        """\
        Clear all KLs from all stores.
        """
        for store in self.storages:
            store._clear()

    def close(self):
        """\
        Close all stores.
        """
        for store in self.storages:
            store.close()
        self.storages = list()

    def flush(self, **kwargs):
        """\
        Flush all stores.
        """
        for store in self.storages:
            store.flush(**kwargs)
