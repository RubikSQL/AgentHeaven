__all__ = [
    "BaseKLEngine",
]

from ..utils.basic.misc_utils import unique
from ..utils.basic.config_utils import HEAVEN_CM
from ..utils.basic.log_utils import get_logger
from ..utils.basic.progress_utils import Progress, TqdmProgress, NoProgress

logger = get_logger(__name__)

from ..ukf.base import BaseUKF

from ..klstore.base import BaseKLStore

from ..tool.mixin import ToolRegistry


from abc import ABC, abstractmethod
from typing import Optional, Union, List, Dict, Any, Iterable, Callable, Type


class BaseKLEngine(ToolRegistry, ABC):
    """\
    An abstract base class for KLEngine implementations.

    This class provides a protocol for indexing/searching Knowledge items. Each class should provide a list of retrieval methods with prefix `_search_`, which will be viewed together as a toolkit of this engine.

    Subclasses must implement the abstract methods for upsert, and may override batch and existence-checking methods for performance optimization.

    Search Methods:
        Subclasses can implement multiple search methods:
        - _search(include, *args, **kwargs): Default search method (required).
        - _search_xxx(include, *args, **kwargs): Named search method for mode "xxx".
        Use search(mode="xxx") to route to the corresponding _search_xxx method.

    Abstract Methods:
        _search(include, *args, **kwargs): Perform a search for KLs in the engine.
        _upsert(kl): Insert or update a KL in the engine.
        _remove(key): Remove a KL from the engine by its key (id). If not applicable, override it with an empty function or an exception.
        _clear(): Clear all KLs from the store.

    Optional Methods:
        _get(kl): Retrieve a KL from the engine.
            Though not required, leaving `_get` unimplemented may lead to unexpected behavior.
            This is recommended if `kl` should be returned by `search` and there is no KLStore attached.
        _post_search(results: List[BaseUKF]) -> List[BaseUKF]:
            Postprocessing for search results. By default, it returns the results unchanged.
    """

    inplace: bool = False  # In-place means that the engine does not hold KLs itself, but only provides `get` capabilities over an attached KLStore.

    def __init__(
        self,
        storage: Optional[BaseKLStore] = None,
        inplace: Optional[bool] = False,
        name: Optional[str] = None,
        condition: Optional[Callable] = None,
        *args,
        **kwargs,
    ):
        """\
        Initialization.

        Args:
            storage: attach KLEngine to a KLStore.
                When attached, the engine will try to retrieve KLs from the store if not found in the engine itself.
                Notice that though attached, operations on the engine will never change the actual KLs in the store.
                Notice that one KLEngine can be attached to only one KLStore at a time, to support multiple KLStores, use `RouterKLStore` or `CascadeKLStore`.
            inplace: Whether the engine is in-place.
                When inplace is True, the engine does not hold KLs itself, but only provides `get` capabilities over an attached KLStore.
                When inplace is True, storage must be a DatabaseKLStore instance.
            name: Name of the KLEngine instance. If None, defaults to "default".
            condition: Optional upsert/insert condition to apply to the KLEngine.
                KLs that do not satisfy the condition will be ignored. If None, all KLs are accepted.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.
        """
        super().__init__()
        self.storage = storage
        self.inplace = bool(inplace)
        self.name = name or "default"
        self.condition = condition or (lambda kl: True)

    def attach(self, storage: BaseKLStore):
        """\
        Attach KLEngine to a KLStore.
        When attached, the engine will try to retrieve KLs from the store if not found in the engine itself.
        Notice that though attached, operations on the engine will never change the actual KLs in the store.
        Notice that one KLEngine can be attached to only one KLStore at a time, to support multiple KLStores, use `RouterKLStore` or `CascadeKLStore`.

        Args:
            storage (BaseKLStore): The KLStore to attach.
        """
        self.storage = storage

    def detach(self):
        """\
        Detach KLEngine from its attached KLStore.
        """
        self.storage = None

    def _get(self, key: Union[int, str, BaseUKF], default: Any = ...) -> BaseUKF:
        return default

    def get(self, key: Union[int, str, BaseUKF], default: Any = ..., storage: Optional[bool] = None) -> BaseUKF:
        """\
        Retrieves a KL by its key.
        By default it tries to get the KL from the engine itself.
        When a KLStore is attached, it will try to get the KL from the store if not found in the engine.

        Args:
            key (Union[int, str, BaseUKF]): The key or BaseUKF instance to retrieve.
            default (Any): The default value to return if the KL is not found.
            storage (bool): Whether to retrieve the KL from the storage. Default is None.
                If `storage` is True, it will always try to get the KL from the store, and bypass the engine.
                If `storage` is False, it will only try to get the KL from the engine, and if not found, it will not try to get the KL from the store.
                If `storage` is None, it will prioritize the engine over the store.
        Returns:
            BaseUKF: The retrieved KL instance if found. Otherwise default.
        """
        if storage:
            return self.storage.get(key, default=default)
        result = self._get(key, default=...)
        if result is not ...:
            return result
        if (storage is None) and (self.storage is not None):
            return self.storage.get(key, default=default)
        return default

    def _has(self, key: int) -> bool:
        if HEAVEN_CM.get("core.debug"):
            logger.warning(
                "The default `_has` implementation of BaseKLEngine determines whether key exists using `__iter__`, which could result in performance issues. Override `_has` or turn off debug mode to suppress this warning."
            )
        return key in set(kl.id for kl in self)

    def __contains__(self, key):
        """Check if a key exists in the engine."""
        if isinstance(key, BaseUKF):
            key = key.id
        if isinstance(key, str):
            key = int(key)
        # if self.inplace:
        #     return key in self.storage
        return self._has(key)

    @abstractmethod
    def _upsert(self, kl: BaseUKF, **kwargs):
        raise NotImplementedError

    def upsert(self, kl: BaseUKF, **kwargs):
        """\
        Upsert a KL.

        Args:
            kl (BaseUKF): The KL to upsert.
            kwargs: Additional keyword arguments.
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
            kwargs: Additional keyword arguments.
        """
        filtered = [kl for kl in kls if self.condition(kl)]
        total = len(filtered)
        progress_cls = progress or NoProgress
        with progress_cls(total=total, desc=f"Upserting KLEngine '{self.name}'") as pbar:
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
            kwargs: Additional keyword arguments.
        """
        filtered = [kl for kl in kls if self.condition(kl)]
        total = len(filtered)
        progress_cls = progress or NoProgress
        with progress_cls(total=total, desc=f"Inserting into KLEngine '{self.name}'") as pbar:
            self._batch_insert(filtered, progress=pbar, **kwargs)
            if pbar.n < total:
                pbar.update(total - pbar.n)

    @abstractmethod
    def _remove(self, key: int, **kwargs):
        raise NotImplementedError

    def __delitem__(self, key: Union[int, str, BaseUKF], **kwargs):
        """\
        Removes a KL from the engine.

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
        Removes a KL from the engine.

        Args:
            key (Union[int, str, BaseUKF]): The key or BaseUKF instance to remove.
            conditioned (bool): Remove only if the KL satisfies the engine's condition. Default is True.
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

    def _batch_remove(self, keys: Iterable[Union[int, str, BaseUKF]], progress: Progress = None, **kwargs):
        keys = unique(keys)  # Keeping only unique keys
        for key in keys:
            self._remove(key, **kwargs)
            if progress is not None:
                progress.update(1)

    def batch_remove(self, keys: Iterable[Union[int, str, BaseUKF]], conditioned: bool = True, progress: Type[Progress] = None, **kwargs):
        """\
        Removes multiple KLs from the engine.

        Args:
            keys (Iterable[Union[int, str, BaseUKF]]): The keys or BaseUKF instances to remove.
            conditioned (bool): Remove only if the KLs satisfy the engine's condition. Default is True.
                Notice that conditioned removal only applies when passing BaseUKF instances in keys.
            progress (Type[Progress]): Progress class for reporting. None for silent, TqdmProgress for terminal.
            **kwargs: Additional keyword arguments.
        """
        parsed_keys = []
        for key in keys:
            if isinstance(key, BaseUKF):
                if conditioned and (not self.condition(key)):
                    continue
                key = key.id
            if isinstance(key, str):
                key = int(key)
            parsed_keys.append(key)
        total = len(parsed_keys)
        progress_cls = progress or NoProgress
        with progress_cls(total=total, desc=f"Removing from KLEngine '{self.name}'") as pbar:
            self._batch_remove(parsed_keys, progress=pbar, **kwargs)
            if pbar.n < total:
                pbar.update(total - pbar.n)

    @abstractmethod
    def _clear(self):
        raise NotImplementedError

    def clear(self):
        """\
        Clears the engine.
        """
        self._clear()

    def close(self):
        """\
        Closes the engine, if applicable.
        """
        pass

    def flush(self):
        """\
        Flushes the engine, if applicable.
        """
        pass

    def sync(self, batch_size: Optional[int] = None, progress: Type[Progress] = None, **kwargs):
        """\
        Synchronize KLEngine with its attached KLStore, if applicable.
        Notice that a whole synchronization can often lead to large data upload/download.
        This could result in performance issues and even errors for particular backends.
        Therefore, parameters like batch_size are provided to control the synchronization process.
        It is recommended to override this method for better performance.

        Args:
            batch_size (Optional[int]): The batch size for synchronization.
                If None, use the default batch size from configuration (512).
                If <= 0, yields all KLs in a single batch.
            progress (Type[Progress]): Progress class for reporting. None for silent, TqdmProgress for terminal.
            **kwargs: Additional keyword arguments.
        """
        self.clear()  # Remove all existing KLs for synchronization
        batch_size = batch_size or HEAVEN_CM.get("klengine.sync_batch_size", 512)
        num_kls = len(self.storage)
        total = num_kls
        batch_iter = self.storage.batch_iter(batch_size=batch_size)
        progress_cls = progress or NoProgress
        with progress_cls(total=total, desc=f"Syncing KLEngine '{self.name}'") as pbar:
            for kl_batch in batch_iter:
                self.batch_upsert(kl_batch, progress=None, **kwargs)
                pbar.update(len(kl_batch))
        self.flush()

    def list_search(self) -> List[Optional[str]]:
        """\
        List all available search methods.

        Returns:
            List[Optional[str]]: A list of search method names. None represents the default search method.
        """
        methods = [None]  # Default _search method
        for attr_name in dir(self.__class__):
            if attr_name.startswith("_search_") and callable(getattr(self.__class__, attr_name)):
                method_name = attr_name[8:]
                methods.append(method_name)
        return methods

    @abstractmethod
    def _search(self, include: Optional[Iterable[str]] = None, *args, **kwargs) -> List[Dict[str, Any]]:
        """\
        Perform a search operation on the engine, return the KLs with keys limited to include.
        Conventionally, it ir recommended use `id` to return `BaseUKF.id`, and `kl` to return `BaseUKF` itself.

        Notice that when `include=None`, the default keys must at least include `id`.

        Args:
            include (Optional[Iterable[str]]): The keys to include in the search results.
            *args: The positional arguments to pass to the search.
            **kwargs: The keyword arguments to pass to the search.

        Returns:
            List[Dict[str, Any]]: The search results.
        """
        pass

    def _post_search(self, results: List[Dict[str, Any]], include: Optional[Iterable[str]] = None, *args, **kwargs) -> List[Dict[str, Any]]:
        """\
        Postprocessing for search results. By default, it returns the results unchanged.

        Args:
            results (List[Dict[str, Any]]): The search results.
            include (Optional[Iterable[str]]): The keys to include in the search results.
            *args: The positional arguments to pass to the search.
            **kwargs: The keyword arguments to pass to the search.

        Returns:
            List[Dict[str, Any]]: The postprocessed search results.
        """
        return results

    def search(
        self,
        *args,
        include: Optional[Iterable[str]] = None,
        mode: Optional[str] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """\
        Perform a search operation on the engine, return the KLs with keys limited to include.
        Conventionally, it ir recommended use `id` to return `BaseUKF.id`, and `kl` to return `BaseUKF` itself.

        Args:
            include (Optional[Iterable[str]]): The keys to include in the search results.
                Defaults to None, which includes at least 'id' and 'kl'.
            mode (Optional[str]): The search method mode to use. None uses the default _search method.
            *args: The positional arguments to pass to the search.
            **kwargs: The keyword arguments to pass to the search.

        Returns:
            List[Dict[str, Any]]: The search results.
        """
        # Route to appropriate search method based on mode
        if mode is None:
            search_method = self._search
        else:
            method_name = f"_search_{mode}"
            if not hasattr(self, method_name) or not callable(getattr(self, method_name)):
                available_modes = [m for m in self.list_search() if m is not None]
                raise ValueError(f"Search mode '{mode}' not found. Available modes: {available_modes}")
            search_method = getattr(self, method_name)

        include_list = None if include is None else unique(list(include))
        requires_kl = (include_list is None) or bool("kl" in include_list)
        include_ext = None if include_list is None else unique(["id"] + include_list)
        results = search_method(*args, include=include_ext, **kwargs)
        if requires_kl:
            # Collect generator results into a list to avoid generator exhaustion
            temp_results = []
            for result in results:
                if result.get("kl", None) is None:
                    result["kl"] = self.get(result["id"], default=None, storage=True)
                temp_results.append(result)
            results = [r for r in temp_results if r.get("kl", None) is not None]
        # TODO: For some weird reason this results in a duplicate parameter error
        # results = self._post_search(results, include=include_list, *args, **kwargs)
        if include_list is not None:
            results = [{k: r.get(k, None) for k in include_list} for r in results]
        else:
            results = [{k: r.get(k, None) for k in unique(["id", "kl"] + list(r.keys()))} for r in results]
        for r in results:
            if r.get("kl") and isinstance(r["kl"], BaseUKF):
                r["kl"].metadata |= {
                    "search": {
                        "engine": self.name,
                        "mode": mode,
                        "args": args,
                        "kwargs": kwargs,
                        "returns": {k: v for k, v in r.items() if k not in ["id", "kl"]},
                    }
                }
        return results
