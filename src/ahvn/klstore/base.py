__all__ = [
    "BaseKLStore",
]


from ..utils.basic.misc_utils import unique
from ..utils.basic.config_utils import HEAVEN_CM
from ..utils.basic.log_utils import get_logger
from ..utils.basic.progress_utils import Progress, NoProgress

logger = get_logger(__name__)

from ..ukf.base import BaseUKF

from ..tool.mixin import ToolRegistry

from abc import ABC, abstractmethod
from typing import Optional, Union, Iterable, Any, Generator, Callable, Type


class BaseKLStore(ToolRegistry, ABC):
    """\
    An abstract base class for KLStore implementations.

    This class provides a protocol for storing and managing Knowledge items, each identified by a unique `id` attribute, typically using a `BaseUKF` instance as the storage unit. The class defines the required interface for storage, retrieval, insertion, batch operations, and removal of KL items, as well as iteration and clearing of the store.

    Subclasses must implement the abstract methods for storage and retrieval by id, and may override batch and existence-checking methods for performance optimization.

    Abstract Methods:
        _get(key, default): Retrieve a KL (BaseUKF) by its key (id). Should return `default` (Ellipsis by default) if not found.
        _upsert(kl): Insert or update a KL in the store.
        _remove(key): Remove a KL from the store by its key (id).
        _itervalues(): Return an iterator over all KLs in the store.
        _clear(): Clear all KLs from the store.

    Optional Override Methods:
        _has(key): Determines if a KL exists for the given key.
        __len__(): Returns the number of entries in the store.

    Notes:
        - The default implementations of `__len__`, `_has`, and batch operations are not optimized and may be slow for large stores. Subclasses are encouraged to override these for efficiency.
    """

    name: str

    def __init__(self, name: Optional[str] = None, condition: Optional[Callable] = None, *args, **kwargs):
        """\
        Initialization.

        Args:
            name: Name of the KLStore instance. If None, defaults to "default".
            condition: Optional upsert/insert condition to apply to the KLStore.
                KLs that do not satisfy the condition will be ignored. If None, all KLs are accepted.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.
        """
        super().__init__()
        self.name = name or "default"
        self.condition = condition or (lambda kl: True)

    def _has(self, key: int) -> bool:
        if HEAVEN_CM.get("core.debug"):
            logger.warning(
                "The default `_has` implementation of BaseKLStore determines whether key exists using `__iter__`, which could result in performance issues. Override `_has` or turn off debug mode to suppress this warning."
            )
        return key in set(kl.id for kl in self)

    def __contains__(self, key: Union[int, str, BaseUKF]) -> bool:
        """\
        Checks if a KL exists for the given key.

        Args:
            key (Union[int, str, BaseUKF]): The key or BaseUKF instance to check.

        Returns:
            bool: True if the KL exists, False otherwise.
        """
        if isinstance(key, BaseUKF):
            key = key.id
        if isinstance(key, str):
            key = int(key)
        return self._has(key)

    def exists(self, key: Union[int, str, BaseUKF]) -> bool:
        """\
        Checks if a KL exists for the given key.

        Args:
            key (Union[int, str, BaseUKF]): The key or BaseUKF instance to check.

        Returns:
            bool: True if the KL exists, False otherwise.
        """
        if isinstance(key, BaseUKF):
            key = key.id
        if isinstance(key, str):
            key = int(key)
        return self._has(key)

    @abstractmethod
    def _get(self, key: int, default: Any = ...) -> BaseUKF:
        raise NotImplementedError

    def __getitem__(self, key: Union[int, str, BaseUKF]):
        """\
        Retrieve a KL by its key.

        Args:
            key (Union[int, str, BaseUKF]): The key or BaseUKF instance to retrieve.

        Returns:
            BaseUKF: The retrieved KL instance if found. Otherwise Ellipsis.
        """
        if isinstance(key, BaseUKF):
            key = key.id
        if isinstance(key, str):
            key = int(key)
        kl = self._get(key, default=...)
        return ... if kl is ... else kl

    def get(self, key: Union[int, str, BaseUKF], default: Any = ...):
        """\
        Retrieves a KL by its key.

        Args:
            key (Union[int, str, BaseUKF]): The key or BaseUKF instance to retrieve.
            default (Any): The default value to return if the KL is not found.

        Returns:
            BaseUKF: The retrieved KL instance if found. Otherwise default.
        """
        if isinstance(key, BaseUKF):
            key = key.id
        if isinstance(key, str):
            key = int(key)
        kl = self._get(key, default=...)
        return default if kl is ... else kl

    def _batch_get(self, keys: Iterable[int], default: Any = ...) -> list:
        return [self._get(key, default=default) for key in keys]

    def batch_get(self, keys: Iterable[Union[int, str, BaseUKF]], default: Any = ..., progress: Type[Progress] = None) -> list:
        """\
        Retrieves multiple KLs by their keys.
        The default batch get is not optimized nor parallelized.
        It is recommended to override `_batch_get` for better performance.

        Args:
            keys (Iterable[Union[int, str, BaseUKF]]): The keys or BaseUKF instances to retrieve.
            default (Any): The default value to return if a KL is not found.

        Returns:
            list: A list of retrieved KL instances. Missing KLs are replaced with default.
        """
        parsed_keys = []
        for key in keys:
            if isinstance(key, BaseUKF):
                key = key.id
            if isinstance(key, str):
                key = int(key)
            parsed_keys.append(key)
        progress_cls = progress or NoProgress
        total = len(parsed_keys)
        with progress_cls(total=total, desc=f"Fetching from KLStore '{self.name}'") as pbar:
            result = self._batch_get(parsed_keys, default=default)
            if pbar.n < total:
                pbar.update(total - pbar.n)
        return result

    @abstractmethod
    def _upsert(self, kl: BaseUKF, **kwargs):
        raise NotImplementedError

    def upsert(self, kl: BaseUKF, **kwargs):
        """\
        Upsert a KL.

        Args:
            kl (BaseUKF): The KL to upsert.
            **kwargs: Additional keyword arguments.
        """
        if self.condition(kl):
            self._upsert(kl, **kwargs)

    def _insert(self, kl: BaseUKF, **kwargs):
        if kl.id not in self:
            self._upsert(kl, **kwargs)

    def insert(self, kl: BaseUKF, **kwargs):
        """\
        Insert a KL.

        Args:
            kl (BaseUKF): The KL to insert.
            kwargs: Additional keyword arguments.
        """
        if self.condition(kl):
            self._insert(kl, **kwargs)

    def _batch_upsert(self, kls: Iterable[BaseUKF], progress: Progress = None, **kwargs):
        kls = unique(kls, key=lambda kl: kl.id)  # Keeping only the first occurrence of each ID in case of duplicates
        for kl in kls:
            self._upsert(kl, **kwargs)
            if progress is not None:
                progress.update(1)

    def batch_upsert(self, kls: Iterable[BaseUKF], progress: Type[Progress] = None, **kwargs):
        """\
        Upsert multiple KLs.
        The default batch upsert is not optimized nor parallelized.
        It is recommended to override this method for better performance.

        Args:
            kls (Iterable[BaseUKF]): The KLs to upsert.
            progress (Type[Progress]): Progress class for reporting. None for silent, TqdmProgress for terminal.
            **kwargs: Additional keyword arguments.
        """
        filtered = [kl for kl in kls if self.condition(kl)]
        total = len(filtered)
        progress_cls = progress or NoProgress
        with progress_cls(total=total, desc=f"Upserting KLStore '{self.name}'") as pbar:
            self._batch_upsert(filtered, progress=pbar, **kwargs)
            if pbar.n < total:
                pbar.update(total - pbar.n)

    def _batch_insert(self, kls: Iterable[BaseUKF], progress: Progress = None, **kwargs):
        kls = unique(kls, key=lambda kl: kl.id)  # Keeping only the first occurrence of each ID in case of duplicates
        if hasattr(self, "_batch_upsert"):
            self._batch_upsert([kl for kl in kls if (kl.id not in self)], progress=progress, **kwargs)
            return
        for kl in kls:
            self._insert(kl, **kwargs)
            if progress is not None:
                progress.update(1)

    def batch_insert(self, kls: Iterable[BaseUKF], progress: Type[Progress] = None, **kwargs):
        """\
        Insert multiple KLs.
        The default batch insert first checks for existing keys and then batch upserts.
        When overriding `batch_upsert`, batch insert is automatically optimized.
        Nevertheless, the existence check uses `_has`, which is by default not optimized.
        It is recommended to override `batch_insert` or `_has` for better performance.

        Args:
            kls (Iterable[BaseUKF]): The KLs to insert.
            progress (Type[Progress]): Progress class for reporting. None for silent, TqdmProgress for terminal.
            **kwargs: Additional keyword arguments.
        """
        filtered = [kl for kl in kls if self.condition(kl)]
        total = len(filtered)
        progress_cls = progress or NoProgress
        with progress_cls(total=total, desc=f"Inserting into KLStore '{self.name}'") as pbar:
            self._batch_insert(filtered, progress=pbar, **kwargs)
            if pbar.n < total:
                pbar.update(total - pbar.n)

    @abstractmethod
    def _remove(self, key: int, **kwargs):
        raise NotImplementedError

    def __delitem__(self, key: Union[int, str, BaseUKF], **kwargs):
        """\
        Removes a KL from the store.

        Args:
            key (Union[int, str, BaseUKF]): The key or BaseUKF instance to remove.
            **kwargs: Additional keyword arguments.
        """
        if isinstance(key, BaseUKF):
            key = key.id
        if isinstance(key, str):
            key = int(key)
        self._remove(key, **kwargs)

    def remove(self, key: Union[int, str, BaseUKF], conditioned: bool = True, **kwargs):
        """\
        Removes a KL from the store.

        Args:
            key (Union[int, str, BaseUKF]): The key or BaseUKF instance to remove.
            conditioned (bool): Remove only if the KL satisfies the store's condition. Default is True.
                Notice that conditioned removal only applies when passing a BaseUKF instance as key.
            **kwargs: Additional keyword arguments.
        """
        if isinstance(key, BaseUKF):
            if conditioned and (not self.condition(key)):
                return
            key = key.id
        if isinstance(key, str):
            key = int(key)
        self._remove(key, **kwargs)

    def _batch_remove(self, keys: Iterable[int], progress: Progress = None, **kwargs):
        keys = unique(keys)  # Keeping only unique keys
        for key in keys:
            self._remove(key, **kwargs)
            if progress is not None:
                progress.update(1)

    def batch_remove(self, kls: Iterable[Union[int, str, BaseUKF]], conditioned: bool = True, progress: Type[Progress] = None, **kwargs):
        """\
        Removes multiple KLs from the store.
        The default batch remove is not optimized nor parallelized.
        It is recommended to override this method for better performance.

        Args:
            kls (Iterable[Union[int, str, BaseUKF]]): The keys or BaseUKF instances to remove.
            conditioned (bool): Remove only if the KLs satisfy the store's condition. Default is True.
                Notice that conditioned removal only applies when passing BaseUKF instances in kls.
            progress (Type[Progress]): Progress class for reporting. None for silent, TqdmProgress for terminal.
            **kwargs: Additional keyword arguments.
        """
        keys = []
        for key in kls:
            if isinstance(key, BaseUKF):
                if conditioned and (not self.condition(key)):
                    continue
                key = key.id
            if isinstance(key, str):
                key = int(key)
            keys.append(key)
        total = len(keys)
        progress_cls = progress or NoProgress
        with progress_cls(total=total, desc=f"Removing from KLStore '{self.name}'") as pbar:
            self._batch_remove(keys, progress=pbar, **kwargs)
            if pbar.n < total:
                pbar.update(total - pbar.n)

    def __len__(self) -> int:
        if HEAVEN_CM.get("core.debug"):
            logger.warning(
                "The default `__len__` implementation of BaseKLStore gets the length of `__iter__`, which could result in performance issues. Override `__len__` or turn off debug mode to suppress this warning."
            )
        return len(list(self._itervalues()))

    @abstractmethod
    def _itervalues(self) -> Generator[BaseUKF, None, None]:
        raise NotImplementedError

    def __iter__(self) -> Generator[BaseUKF, None, None]:
        """\
        Iterates over the stored KLs.

        Yields:
            BaseUKF: The stored KLs in the KLStore.
        """
        yield from self._itervalues()

    def batch_iter(self, batch_size: Optional[int] = None, **kwargs):
        """\
        Iterates over the stored KLs in batches.

        Args:
            batch_size (Optional[int]): The size of each batch.
                If None, use the default batch size from configuration (512).
                If <= 0, yields all KLs in a single batch.
            **kwargs: Additional keyword arguments.
        """
        batch_size = batch_size or HEAVEN_CM.get("klstore.batch_size", 512)
        if batch_size <= 0:
            yield list(self)
            return
        batch = list()
        for i, kl in enumerate(self, start=1):
            if i % batch_size == 0:
                yield batch
                batch = list()
            batch.append(kl)
        if batch:
            yield batch

    @abstractmethod
    def _clear(self):
        raise NotImplementedError

    def clear(self):
        """\
        Clears the store.
        """
        self._clear()

    def close(self):
        """\
        Closes the store, if applicable.
        """
        pass

    def flush(self):
        """\
        Flushes the store, if applicable.
        """
        pass
