__all__ = [
    "ScanKLEngine",
]

from typing import Any, Dict, Iterable, List, Optional, Callable

from ..utils.klop import KLOp
from ..utils.basic.log_utils import get_logger

logger = get_logger(__name__)

from .base import BaseKLEngine
from ..ukf.base import BaseUKF
from ..klstore.base import BaseKLStore


class ScanKLEngine(BaseKLEngine):
    """\
    A brute-force scan KLEngine implementation with zero storage overhead.

    This engine performs search by scanning through the entire attached KLStore
    and using `eval_filter` on each KL to find matches. It is always inplace
    and supports all kinds of KLStores.

    This is the simplest possible search engine - no indexing, no optimization,
    just linear scan. Useful for small datasets or as a fallback.

    Search Methods:
        _search(topk, offset, include, **kwargs): Perform brute-force scan using eval_filter.

    Abstract Methods (inherited from BaseKLEngine):
        _upsert(kl): No-op (always inplace).
        _remove(key): No-op (always inplace).
        _clear(): No-op (always inplace).
    """

    inplace: bool = True
    recoverable: bool = True

    def __init__(
        self,
        storage: BaseKLStore,
        name: Optional[str] = None,
        condition: Optional[Callable] = None,
        *args,
        **kwargs,
    ):
        """Initialize the ScanKLEngine.

        Args:
            storage: attach ScanKLEngine to a BaseKLStore (required).
            name: Name of the KLEngine instance. If None, defaults to "{storage.name}_scan_idx".
            condition: Optional upsert/insert condition to apply to the KLEngine.
                KLs that do not satisfy the condition will be ignored. If None, all KLs are accepted.
            *args: Additional positional arguments passed to ScanKLEngine.
            **kwargs: Additional keyword arguments passed to ScanKLEngine.
        """
        super().__init__(
            storage=storage,
            inplace=True,
            name=name or f"{storage.name}_scan_idx",
            condition=condition,
            *args,
            **kwargs,
        )
        self.exprs = None if not kwargs.get("facets") else KLOp.expr(**kwargs.get("facets"))

    def _has(self, key: int) -> bool:
        """\
        Check if a KL with the given key exists in the storage.

        Args:
            key (int): The unique identifier of the KL.

        Returns:
            bool: True if the KL exists, False otherwise.
        """
        return key in self.storage

    def __len__(self) -> int:
        """\
        Return the number of KLs in the storage.

        Returns:
            int: The number of KLs in the storage.
        """
        return len(self.storage)

    def __iter__(self):
        """\
        Iterate over all KLs in the storage.
        """
        return iter(self.storage)

    def _search(
        self,
        topk: Optional[int] = None,
        offset: Optional[int] = None,
        include: Optional[Iterable[str]] = None,
        *args,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """\
        Perform a brute-force scan search using eval_filter.

        This method scans through the entire storage and evaluates each KL
        against the filter conditions using `eval_filter`.

        Args:
            topk (Optional[int]): Maximum number of results to return.
                If None, returns all matching results. Defaults to None.
            offset (Optional[int]): Number of results to skip.
                If None, starts from the first result. Defaults to None.
            include (Optional[Iterable[str]]): The keys to include in the search results.
                Supported keys include:
                - 'id': The unique identifier of the KL (BaseUKF.id).
                - 'kl': The KL object itself (BaseUKF).
                Defaults to None, which resolves to ['id', 'kl'].
            *args: Additional positional arguments.
            **kwargs: Facet filter conditions as keyword arguments.

        Returns:
            List[Dict[str, Any]]: The search results matching the applied filters.
        """
        include_set = set(include) if include is not None else {"id", "kl"}

        # Build combined filter expression
        if self.exprs is not None:
            if kwargs:
                kwargs_expr = KLOp.expr(**kwargs)
                combined_expr = {"AND": [self.exprs, kwargs_expr]}
            else:
                combined_expr = self.exprs
        else:
            combined_expr = KLOp.expr(**kwargs) if kwargs else None

        results = []
        skipped = 0
        offset = offset or 0

        for kl in self.storage:
            # Evaluate filter
            if combined_expr is not None:
                if not kl.eval_filter(combined_expr):
                    continue

            # Handle offset
            if skipped < offset:
                skipped += 1
                continue

            # Build result dict
            result = {"id": kl.id}
            if "kl" in include_set:
                result["kl"] = kl

            results.append(result)

            # Check topk limit
            if topk is not None and len(results) >= topk:
                break

        return results

    def _get(self, key: int, default: Any = ...) -> Optional[BaseUKF]:
        """\
        Retrieve a KL from the storage.

        Args:
            key (int): The unique identifier of the KL.
            default (Any): The default value to return if not found.

        Returns:
            Optional[BaseUKF]: The KL if found, otherwise default.
        """
        return self.storage.get(key, default=default)

    def _upsert(self, kl: BaseUKF, **kwargs):
        """No-op: ScanKLEngine is always inplace."""
        return

    def _remove(self, key: int, **kwargs):
        """No-op: ScanKLEngine is always inplace."""
        return

    def _clear(self):
        """No-op: ScanKLEngine is always inplace."""
        return
