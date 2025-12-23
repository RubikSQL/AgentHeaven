"""\
Abstract cache protocol and common helpers.

Implements the CacheEntry structure and BaseCache with memoization decorators for
sync/async functions and streaming generators.
"""

__all__ = [
    "CacheEntry",
    "BaseCache",
]

from ..utils.basic.hash_utils import md5hash
from ..utils.basic.config_utils import HEAVEN_CM
from ..utils.basic.log_utils import get_logger

logger = get_logger(__name__)

import inspect
import functools

from abc import ABC, abstractmethod
from typing import Any, Dict, Callable, Optional, Union, Iterable, Generator, AsyncGenerator, List
from dataclasses import dataclass, field
from copy import deepcopy


@dataclass
class CacheEntry(object):
    """\
    A universal object to store cache entries, containing the function (name), inputs, output, and optional metadata.
    """

    func: str
    inputs: Dict[str, Any] = field(default_factory=dict)
    output: Any = ...
    expected: Any = ...
    metadata: Optional[Dict[str, Any]] = field(default_factory=dict)
    _key: int = None

    def __post_init__(self):
        self._key = md5hash(self.inputs, salt=self.func)
        self.metadata = self.metadata or dict()

    @property
    def key(self):
        return self._key

    @property
    def value(self):
        return self.output if self.expected is ... else self.expected

    @classmethod
    def from_args(
        cls,
        func: Union[Callable, str] = "",
        output: Any = ...,
        expected: Any = ...,
        metadata: Optional[Dict[str, Any]] = None,
        exclude: Optional[Iterable[str]] = None,
        **inputs: Any,
    ) -> "CacheEntry":
        """\
        Creates a CacheEntry from function arguments.

        Args:
            func (Union[Callable, str]): The function or its name to be cached.
            output (Any): The output of the function.
            expected (Any): The expected output of the function.
            metadata (Optional[Dict[str, Any]]): Optional metadata to store with the cache entry
            exclude (Optional[Iterable[str]]): Keys to exclude from inputs.
            **inputs: Arbitrary keyword arguments representing the inputs to the function.
        """
        _exclude = set(exclude) if exclude else set()
        _inputs = {k: v for k, v in inputs.items() if k not in _exclude}
        return cls(
            func=func.__name__ if callable(func) else str(func),
            inputs=_inputs,
            output=output,
            expected=expected,
            metadata=metadata,
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any], exclude: Optional[Iterable[str]] = None) -> "CacheEntry":
        """\
        Creates a CacheEntry from a dictionary.

        Args:
            data (Dict[str, Any]): The dictionary containing the cache entry data.
            exclude (Optional[Iterable[str]]): Keys to exclude from inputs.
        """
        return cls.from_args(
            func=data.get("func", ""),
            output=data.get("output", ...),
            expected=data.get("expected", ...),
            metadata=data.get("metadata"),
            exclude=exclude,
            **data.get("inputs", dict()),
        )

    def to_dict(self) -> Dict[str, Any]:
        """\
        Converts the CacheEntry to a dictionary.

        Returns:
            Dict[str, Any]: A dictionary representation of the CacheEntry.
        """
        return (
            {
                "func": self.func,
                "inputs": self.inputs,
            }
            | ({} if self.output is ... else {"output": self.output})
            | ({} if self.expected is ... else {"expected": self.expected})
            | {
                "metadata": self.metadata,
            }
        )

    def clone(self, **updates) -> "CacheEntry":
        """\
        Creates a clone of the CacheEntry with optional updates to its attributes.

        Args:
            **updates: Arbitrary keyword arguments to update the CacheEntry attributes.

        Returns:
            CacheEntry: A new CacheEntry instance with updated attributes.
        """
        exclude = updates.get("exclude")
        filtered = {k: v for k, v in updates.items() if k in ["func", "inputs", "output", "expected", "metadata"]}
        return self.__class__.from_dict(data=self.to_dict() | filtered, exclude=exclude)

    def annotate(self, expected: Any = ..., metadata: Optional[Dict[str, Any]] = None) -> "CacheEntry":
        """\
        Annotates the CacheEntry with expected output and metadata.

        Args:
            expected (Any): The expected output of the function. If omitted, will use the actual output as annotation.
            metadata (Optional[Dict[str, Any]]): Optional metadata to store with the cache entry.

        Returns:
            CacheEntry: A new CacheEntry instance with the annotation.
        """
        if expected is ...:
            expected = self.output
        return self.clone(expected=expected, metadata=self.metadata | (metadata or dict()))

    @property
    def annotated(self) -> bool:
        """\
        Checks if the CacheEntry has been annotated with expected output.

        Returns:
            bool: True if the CacheEntry has an expected output, False otherwise.
        """
        return self.expected is not ...


class BaseCache(ABC):
    """\
    An abstract base class for cache implementations.

    The class provides `memoize` and `batch_memoize` decorators to cache function results.
    The class requires subclasses to implement storage and retrieval methods.
    The caching supports both synchronous and asynchronous functions.

    Attributes:
        _cache (Dict[str, CacheEntry]): A dictionary to store cache entries.

    Abstract Methods:
        _get(key, default): Retrieves a dict (CacheEntry) from the cache by its key. Use `Ellipsis` as default to raise KeyError if not found (to avoid collisions with functions returning None).
        _set(key, value): Sets a cache entry in the cache.
        _remove(key): Removes a cache entry from the cache by its key.
        _itervalues(): Returns an iterator over the values in the cache.
        _clear(): Clears the cache.

    Optional Override Methods:
        _has(key): Determines if a cache entry exists for the given key.
        __len__(): Returns the number of entries in the cache.

    Notes:
        - The default implementations of `__len__`, `_has`, and batch operations are not optimized and may be slow for large stores. Subclasses are encouraged to override these for efficiency.
        - It is worth noticing that only the `__getitem__` (implemented by `_get`) and `add` (implemented by `_set`) are used during memoize.
    """

    def __init__(self, exclude: Optional[Iterable[str]] = None, *args, **kwargs):
        """\
        Initialization.

        Args:
            exclude (Optional[Iterable[str]]): Keys to exclude from inputs when creating cache entries.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.
        """
        super().__init__()
        self.set_exclude(exclude=exclude)

    def set_exclude(self, exclude: Optional[Iterable[str]] = None):
        """\
        Set the keys to exclude from inputs when creating cache entries.

        Args:
            exclude (Optional[Iterable[str]]): Keys to exclude from inputs when creating cache entries.
        """
        self._exclude = deepcopy(set(exclude)) if exclude else set()

    def add_exclude(self, exclude: Optional[Iterable[str]] = None):
        """\
        Add keys to exclude from inputs when creating cache entries.

        Args:
            exclude (Optional[Iterable[str]]): Keys to add to the exclusion list.
        """
        self._exclude.update(deepcopy(set(exclude)) if exclude else set())

    def _has(self, key: int) -> bool:
        if HEAVEN_CM.get("core.debug"):
            logger.warning(
                "The default `_has` implementation of BaseCache determines whether key exists using `__iter__`, which could result in performance issues. Override `_has` or turn off debug mode to suppress this warning."
            )
        return key in set(entry.key for entry in self)

    def __contains__(self, key: Union[int, str, CacheEntry]) -> bool:
        """\
        Checks if a cache entry exists for the given key.

        Args:
            key (Union[int, CacheEntry]): The key or CacheEntry to check in the cache.

        Returns:
            bool: True if the cache entry exists, False otherwise.
        """
        if isinstance(key, CacheEntry):
            return self._has(key.key)
        if isinstance(key, str):
            key = int(key)
        return self._has(key)

    def exists(self, func: Union[Callable, str], **kwargs) -> bool:
        """\
        Checks if a cache entry exists for the given function and inputs.

        Args:
            func (Union[Callable, str]): The function or its name to check in the cache.
            **kwargs: Arbitrary keyword arguments representing the inputs to the function.

        Returns:
            bool: True if the cache entry exists, False otherwise.
        """
        return self._has(CacheEntry.from_args(func=func, exclude=self._exclude, **kwargs).key)

    @abstractmethod
    def _get(self, key: int, default: Any = ...) -> Dict[str, Any]:
        raise NotImplementedError

    def __getitem__(self, key: Union[int, str, CacheEntry]) -> CacheEntry:
        """\
        Retrieves a cache entry for the given function and inputs.

        Args:
            key (Union[int, str, CacheEntry]): The key or CacheEntry to retrieve.

        Returns:
            CacheEntry: The cached entry if found. Otherwise Ellipsis.
        """
        if isinstance(key, CacheEntry):
            key = key.key
        if isinstance(key, str):
            key = int(key)
        data = self._get(key, default=...)
        return ... if data is ... else CacheEntry.from_dict(data)

    def retrieve(self, func: Union[Callable, str], **kwargs) -> CacheEntry:
        """\
        Retrieves a cached entry for the given function and inputs.

        Args:
            func (Union[Callable, str]): The function or its name to retrieve the cached value for.
            **kwargs: Arbitrary keyword arguments representing the inputs to the function.

        Returns:
            Any: The cached output if found, otherwise `Ellipsis` (to avoid collisions with functions returning None).
        """
        return self[CacheEntry.from_args(func=func, exclude=self._exclude, **kwargs).key]

    def get(self, func: Union[Callable, str], **kwargs) -> Any:
        """\
        Gets a cached value for the given function and inputs.

        Args:
            func (Union[Callable, str]): The function or its name to retrieve the cached value for.
            **kwargs: Arbitrary keyword arguments representing the inputs to the function.

        Returns:
            Any: The cached output if found, otherwise `Ellipsis` (to avoid collisions with functions returning None).
        """
        entry = self.retrieve(func=func, **kwargs)
        if entry is not ...:
            return entry.value
        return ...

    @abstractmethod
    def _set(self, key: int, value: Dict[str, Any]):
        raise NotImplementedError

    def __setitem__(self, key: Union[int, str, CacheEntry], value: Union[Dict[str, Any], CacheEntry]):
        """\
        Sets a cache entry for the given function and inputs.

        Args:
            key (Union[int, str, CacheEntry]): The key or CacheEntry to set.
            value (Union[Dict[str, Any], CacheEntry]): The value to cache.
        """
        if isinstance(key, CacheEntry):
            key = key.key
        if isinstance(key, str):
            key = int(key)
        if isinstance(value, CacheEntry):
            value = value.to_dict()
        self._set(key, value)

    def set(
        self,
        func: Union[Callable, str],
        output: Any = ...,
        expected: Any = ...,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """\
        Sets a cached value for the given function and inputs.

        Args:
            func (Union[Callable, str]): The function or its name to cache the value for.
            output (Any): The output to cache.
            expected (Any): The expected output of the function.
            metadata (Optional[Dict[str, Any]]): Optional metadata to store with the cache entry.
            **kwargs: Arbitrary keyword arguments representing the inputs to the function.
        """
        entry = CacheEntry.from_args(func=func, output=output, expected=expected, metadata=metadata, exclude=self._exclude, **kwargs)
        self._set(entry.key, entry.to_dict())

    def add(self, entry: CacheEntry):
        """\
        Sets a cache entry by directly adding it to the cache.

        Args:
            entry (CacheEntry): The cache entry to add.
        """
        self._set(entry.key, entry.to_dict())

    def annotate(self, func: Union[Callable, str], expected: Any = ..., metadata: Optional[Dict[str, Any]] = None, **kwargs):
        """\
        Annotates a cached value for the given function and inputs.

        Args:
            func (Union[Callable, str]): The function or its name to annotate the cached value for.
            expected (Any): The expected output of the function.
                If the cache entry exists, its `expected` will be modified, but its `output` will remain unchanged.
                Otherwise, a new entry with `output` and `expected` both set as the annotation will be created.
                If set to `...` and the cache entry exists, it will use the actual output as the annotation.
                If set to `...` but the cache entry does not exist, raise an error.
            metadata (Optional[Dict[str, Any]]): Optional metadata to store with the cache entry.
            **kwargs: Arbitrary keyword arguments representing the inputs to the function.

        Raises:
            ValueError: If the original cache entry does not exist and expected is not provided.
        """
        entry = self.retrieve(func=func, **kwargs)
        if entry is ...:
            if expected is ...:
                raise ValueError(
                    f"The original cache entry does not exist. Expected output must be provided for annotation.\nFunction: {func}\nInputs: {kwargs}"
                )
            self.set(func=func, output=expected, expected=expected, metadata=metadata, **kwargs)
        else:
            self.add(entry.annotate(expected=expected, metadata=metadata))

    @abstractmethod
    def _remove(self, key: int):
        raise NotImplementedError

    def __delitem__(self, key: Union[int, str, CacheEntry]):
        """\
        Deletes a cache entry for the given function and inputs.

        Args:
            key (Union[int, str, CacheEntry]): The key or CacheEntry of the cache entry to delete.
        """
        if isinstance(key, CacheEntry):
            key = key.key
        if isinstance(key, str):
            key = int(key)
        self._remove(key)

    def unset(self, func: Union[Callable, str], **kwargs):
        """\
        Deletes a cache entry for the given function and inputs.

        Args:
            func (Union[Callable, str]): The function or its name to delete the cache entry for.
            **kwargs: Arbitrary keyword arguments representing the inputs to the function.
        """
        self._remove(CacheEntry.from_args(func=func, exclude=self._exclude, **kwargs).key)

    def remove(self, entry: CacheEntry):
        """\
        Deletes a cache entry by directly removing it from the cache.

        Args:
            entry (CacheEntry): The cache entry to remove.
        """
        self._remove(entry.key)

    def __len__(self) -> int:
        if HEAVEN_CM.get("core.debug"):
            logger.warning(
                "The default `__len__` implementation of BaseCache gets the length of `__iter__`, which could result in performance issues. Override `__len__` or turn off debug mode to suppress this warning."
            )
        return len(list(self._itervalues()))

    @abstractmethod
    def _itervalues(self) -> Generator[Dict[str, Any], None, None]:
        raise NotImplementedError

    def __iter__(self) -> Generator[CacheEntry, None, None]:
        """\
        Iterates over the cache entries.

        Yields:
            CacheEntry: The CacheEntry objects in the cache.
        """
        for data in self._itervalues():
            yield CacheEntry.from_dict(data)

    def pop(self) -> Optional[CacheEntry]:
        """\
        Pops an arbitrary cache entry from the cache.

        Returns:
            Optional[CacheEntry]: The popped CacheEntry if the cache is not empty, otherwise None.
        """
        try:
            entry = next(iter(self))
            self._remove(entry.key)
            return entry
        except StopIteration:
            return None

    def popall(self) -> List[CacheEntry]:
        """\
        Pops all cache entries from the cache.

        Returns:
            List[CacheEntry]: A list of all popped CacheEntry objects.
        """
        return [entry for entry in self if self._remove(entry.key) is None]

    @abstractmethod
    def _clear(self):
        raise NotImplementedError

    def clear(self):
        """\
        Clears the cache.
        """
        self._clear()

    def close(self):
        """\
        Closes the cache, if applicable.
        """
        pass

    def flush(self, **kwargs):
        """\
        Flushes the cache, if applicable.
        """
        pass

    def memoize(self, func: Optional[Callable] = None, *, name: Optional[str] = None) -> Callable:
        """\
        Decorator (or decorator factory) to cache the output of a function based on its inputs.

        Usage:
            @cache.memoize
            def f(...): ...

            @cache.memoize(name="xxx")
            def g(...): ...

        When `name` is provided, it is used as the function identifier in the cache key.
        Otherwise, the wrapped function's name is used.
        """

        def _decorate(f: Callable) -> Callable:
            sig = inspect.signature(f)
            is_async_func = inspect.iscoroutinefunction(f)
            is_async_generator = inspect.isasyncgenfunction(f)
            is_sync_generator = inspect.isgeneratorfunction(f)

            if is_async_generator:
                return self._memoize_async_streaming(f, sig, name)
            if is_async_func:
                return self._memoize_async_non_streaming(f, sig, name)
            if is_sync_generator:
                return self._memoize_sync_streaming(f, sig, name)
            return self._memoize_sync_non_streaming(f, sig, name)

        if func is None:
            return _decorate
        return _decorate(func)

    def _memoize_async_non_streaming(self, func: Callable, sig: inspect.Signature, name: Optional[str] = None) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            try:
                bound = sig.bind(*args, **kwargs)
            except TypeError as e:
                logger.error(f"Failed to bind arguments for caching {func.__name__}: {e}")
                return await func(*args, **kwargs)
            bound.apply_defaults()
            entry = CacheEntry.from_args(func=name or func, exclude=self._exclude, **bound.arguments)
            data = self.get(func=name or func, **bound.arguments)
            if data is not ...:
                return data
            output = await func(*args, **kwargs)
            self.add(entry.clone(output=output))
            return output

        return wrapper

    def _memoize_async_streaming(self, func: Callable, sig: inspect.Signature, name: Optional[str] = None) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> AsyncGenerator[Any, None]:
            try:
                bound = sig.bind(*args, **kwargs)
            except TypeError as e:
                logger.error(f"Failed to bind arguments for caching {func.__name__}: {e}")
                async for item in func(*args, **kwargs):
                    yield item
                return
            bound.apply_defaults()
            entry = CacheEntry.from_args(func=name or func, exclude=self._exclude, **bound.arguments)
            data = self.get(func=name or func, **bound.arguments)
            if data is not ...:
                for item in data or list():
                    yield item
                return
            output = []
            async for item in func(*args, **kwargs):
                output.append(item)
                yield item
            self.add(entry.clone(output=output))
            return

        return wrapper

    def _memoize_sync_non_streaming(self, func: Callable, sig: inspect.Signature, name: Optional[str] = None) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                bound = sig.bind(*args, **kwargs)
            except TypeError as e:
                logger.error(f"Failed to bind arguments for caching {func.__name__}: {e}")
                return func(*args, **kwargs)
            bound.apply_defaults()
            entry = CacheEntry.from_args(func=name or func, exclude=self._exclude, **bound.arguments)
            data = self.get(func=name or func, **bound.arguments)
            if data is not ...:
                return data
            output = func(*args, **kwargs)
            self.add(entry.clone(output=output))
            return output

        return wrapper

    def _memoize_sync_streaming(self, func: Callable, sig: inspect.Signature, name: Optional[str] = None) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Generator[Any, None, None]:
            try:
                bound = sig.bind(*args, **kwargs)
            except TypeError as e:
                logger.error(f"Failed to bind arguments for caching {func.__name__}: {e}")
                yield from func(*args, **kwargs)
                return
            bound.apply_defaults()
            entry = CacheEntry.from_args(func=name or func, exclude=self._exclude, **bound.arguments)
            data = self.get(func=name or func, **bound.arguments)
            if data is not ...:
                yield from (data or list())
                return
            output = []
            for item in func(*args, **kwargs):
                output.append(item)
                yield item

            self.add(entry.clone(output=output))
            return

        return wrapper

    def batch_memoize(self, func: Optional[Callable] = None, *, name: Optional[str] = None) -> Callable:
        """\
        Decorator (or decorator factory) to cache the output of a function based on its inputs in batch mode.

        Usage:
            @cache.batch_memoize
            def f(...): ...

            @cache.batch_memoize(name="xxx")
            def g(...): ...

        Args:
            func (Callable): The function to cache.
            name (Optional[str]): Optional name for the function in the cache key.

        Returns:
            Callable: The wrapped function with batch caching.
        """

        def _decorate(f: Callable) -> Callable:
            sig = inspect.signature(f)
            is_async_func = inspect.iscoroutinefunction(f)
            is_async_generator = inspect.isasyncgenfunction(f)
            is_sync_generator = inspect.isgeneratorfunction(f)

            if is_async_generator or is_sync_generator:
                raise ValueError("Batch memoization does not support streaming functions.")

            if is_async_func:
                return self._batch_memoize_async(f, sig, name)
            return self._batch_memoize_sync(f, sig, name)

        if func is None:
            return _decorate
        return _decorate(func)

    def _batch_memoize_async(self, func: Callable, sig: inspect.Signature, name: Optional[str] = None) -> Callable:
        @functools.wraps(func)
        async def wrapper(batch: List[Any], *args, **kwargs) -> List[Any]:
            if not batch:
                return list()
            try:
                bound_args_list = [sig.bind([x], *args, **kwargs) for x in batch]
            except TypeError as e:
                logger.error(f"Failed to bind arguments for batch caching {func.__name__}: {e}")
                return await func(batch, *args, **kwargs)
            for bound in bound_args_list:
                bound.apply_defaults()
            entries = [CacheEntry.from_args(func=name or func, exclude=self._exclude, **bound.arguments) for bound in bound_args_list]
            keys = [entry.key for entry in entries]
            cached_results, uncached_indices = dict(), list()
            for i, key in enumerate(keys):
                data = self.get(func=name or func, **bound_args_list[i].arguments)
                if data is not ...:
                    cached_results[key] = data
                else:
                    uncached_indices.append(i)
            uncached_batch = [batch[i] for i in uncached_indices]
            if uncached_batch:
                uncached_outputs = await func(uncached_batch, *args, **kwargs)
                if len(uncached_outputs) != len(uncached_indices):
                    raise ValueError(f"Function {func.__name__} returned {len(uncached_outputs)} outputs for {len(uncached_indices)} inputs.")
                for i, output in zip(uncached_indices, uncached_outputs):
                    key = entries[i].key
                    entry = entries[i].clone(output=output)
                    self.add(entry)
                    cached_results[key] = output
            return [cached_results.get(key, None) for key in keys]

        return wrapper

    def _batch_memoize_sync(self, func: Callable, sig: inspect.Signature, name: Optional[str] = None) -> Callable:
        @functools.wraps(func)
        def wrapper(batch: List[Any], *args, **kwargs) -> List[Any]:
            if not batch:
                return list()
            try:
                bound_args_list = [sig.bind([x], *args, **kwargs) for x in batch]
            except TypeError as e:
                logger.error(f"Failed to bind arguments for batch caching {func.__name__}: {e}")
                return func(batch, *args, **kwargs)
            for bound in bound_args_list:
                bound.apply_defaults()
            entries = [CacheEntry.from_args(func=name or func, exclude=self._exclude, **bound.arguments) for bound in bound_args_list]
            keys = [entry.key for entry in entries]
            cached_results, uncached_indices = dict(), list()
            for i, key in enumerate(keys):
                data = self.get(func=name or func, **bound_args_list[i].arguments)
                if data is not ...:
                    cached_results[key] = data
                else:
                    uncached_indices.append(i)
            uncached_batch = [batch[i] for i in uncached_indices]
            if uncached_batch:
                uncached_outputs = func(uncached_batch, *args, **kwargs)
                if len(uncached_outputs) != len(uncached_indices):
                    raise ValueError(f"Function {func.__name__} returned {len(uncached_outputs)} outputs for {len(uncached_indices)} inputs.")
                for i, output in zip(uncached_indices, uncached_outputs):
                    key = entries[i].key
                    entry = entries[i].clone(output=output)
                    self.add(entry)
                    cached_results[key] = output
            return [cached_results.get(key, None) for key in keys]

        return wrapper
