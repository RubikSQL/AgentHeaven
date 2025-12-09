__all__ = [
    "FacetKLEngine",
]

from typing import Any, Dict, Iterable, List, Optional, Callable
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..utils.db import Database
from ..utils.db.compiler import SQLCompiler
from ..utils.klop import KLOp
from ..utils.basic.config_utils import HEAVEN_CM
from ..utils.basic.log_utils import get_logger
from ..utils.basic.debug_utils import raise_mismatch
from ..utils.basic.progress_utils import Progress

logger = get_logger(__name__)

from .base import BaseKLEngine
from ..ukf.base import BaseUKF
from ..adapter.db import ORMUKFAdapter
from ..klstore.db_store import DatabaseKLStore


class FacetKLEngine(BaseKLEngine):
    """\
    A faceted search KLEngine implementation that provides multiple search interfaces.

    This class extends BaseKLEngine with three specialized search methods:
    - ORM-like filter-based search through the default _search method
    - Raw SQL query execution through _search_sql method

    The engine is designed to work with structured data that can be filtered using
    various facets (categorical attributes) and supports both programmatic and
    natural language querying interfaces.

    Search Methods:
        _search_facet(topk, offset, include, **kwargs): Perform faceted search using ORM-like filters.
        _search = _search_facet: Alias for _search_facet for default search behavior.

    Abstract Methods (inherited from BaseKLEngine):
        _upsert(kl): Insert or update a KL in the engine.
        _remove(key): Remove a KL from the engine by its key (id).
        _clear(): Clear all KLs from the engine.
    """

    inplace: bool = True
    recoverable: bool = True

    def __init__(
        self,
        storage: DatabaseKLStore,
        inplace: bool = True,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        facets: Dict[str, Any] = None,
        name: Optional[str] = None,
        condition: Optional[Callable] = None,
        *args,
        **kwargs,
    ):
        """Initialize the FacetKLEngine.

        Args:
            storage: attach FacetKLEngine to a DatabaseKLStore (required).
            inplace: If True, search directly on storage database; if False, create a copied table with included f
            include (if inplace=False): List of BaseUKF field names to include. If None, includes all fields. Default is None.
            exclude (if inplace=False): List of BaseUKF field names to exclude. If None, excludes no fields. Default is None.
                Notice that exclude is applied after include, so if a field is in both include and exclude,
                it will be excluded. It is recommended to use only one of include or exclude.
            facets: global facets that will be applied to all searches.
            name: Name of the KLEngine instance. If None, defaults to "{storage.name}_facet_idx".
            condition: Optional upsert/insert condition to apply to the KLEngine.
                KLs that do not satisfy the condition will be ignored. If None, all KLs are accepted.
            *args: Additional positional arguments passed to FacetKLEngine.
            **kwargs: Additional keyword arguments passed to FacetKLEngine.
        """
        if inplace and not isinstance(storage, DatabaseKLStore):
            raise ValueError("When inplace=True, storage must be a DatabaseKLStore instance")

        super().__init__(storage=storage, inplace=inplace, name=name or f"{storage.name}_facet_idx", condition=condition, *args, **kwargs)
        self.exprs = None if not facets else KLOp.expr(**facets)

        if self.inplace:
            self.db = self.storage.db
            self.adapter = self.storage.adapter
        else:
            provider = kwargs.get("provider") or HEAVEN_CM.get("db.default_provider")
            database = kwargs.get("database") or HEAVEN_CM.get(f"db.providers.{provider}.database")
            connection_args = {k: v for k, v in kwargs.items() if k not in ["database", "provider"]}
            self.db = Database(database=database, provider=provider, **connection_args)
            self.adapter = ORMUKFAdapter(name=self.name, include=include, exclude=exclude)
            self._init()

        self.recoverable = self.adapter.recoverable

    def _init(self):
        DatabaseKLStore._init(self)

    def _bulk_add_entities(self, session: Session, kls: list[BaseUKF]):
        DatabaseKLStore._bulk_add_entities(self, session, kls)

    def _remove_dim(self, session: Session, ukf_ids: Optional[Iterable[int]] = None):
        DatabaseKLStore._remove_dim(self, session, ukf_ids)

    def _has(self, key: int) -> bool:
        """\
        Check if a KL with the given key exists in the engine.

        Args:
            key (int): The unique identifier of the KL.

        Returns:
            bool: True if the KL exists, False otherwise.
        """
        return DatabaseKLStore._has(self, key)

    def __len__(self) -> int:
        """\
        Return the number of KLs in the engine.

        Returns:
            int: The number of KLs in the engine.
        """
        if self.inplace:
            return len(self.storage)
        else:
            return DatabaseKLStore.__len__(self)

    def _parse_orderby(self, stmt, orderby: Iterable[str]):
        for field in orderby:
            desc = field.startswith("-")
            field_name = field[1:] if desc else field
            column = getattr(self.adapter.main, field_name, None)
            if column is None:
                raise ValueError(f"Order by field '{field_name}' not found in schema.")
            stmt = stmt.order_by(column.desc() if desc else column.asc())
        return stmt

    def _search_facet(
        self,
        topk: Optional[int] = None,
        offset: Optional[int] = None,
        orderby: Optional[Iterable[str]] = None,
        include: Optional[Iterable[str]] = None,
        *args,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """\
        Perform a faceted search using ORM-like filter expressions.

        This method applies structured filters to search through the knowledge items.
        Filters are combined using AND logic to create faceted search capabilities.

        Args:
            topk (Optional[int]): Maximum number of results to return (SQL LIMIT).
                If None, returns all matching results. Defaults to None.
            offset (Optional[int]): Number of results to skip (SQL OFFSET).
                If None, starts from the first result. Defaults to None.
            orderby (Optional[Iterable[str]]): List of fields to order the results by.
                Each field can be prefixed with '-' for descending order. Defaults to None (no specific order).
            include (Optional[Iterable[str]]): The keys to include in the search results.
                Supported keys include:
                - 'id': The unique identifier of the KL (BaseUKF.id).
                - 'kl': The KL object itself (BaseUKF).
                - 'sql': The generated SQLAlchemy SELECT statement for debugging.
                Defaults to None, which resolves to ['id', 'kl'].
            *args: Additional positional arguments.
            **kwargs: Facet filter conditions as keyword arguments.

        Returns:
            List[Dict[str, Any]]: The search results matching the applied filters.

        Raises:
            NotImplementedError: This method must be implemented by subclasses.
            ValueError: If filter fields are not in schema when not inplace.
        """
        fields = set(self.adapter.fields)
        for field_name in kwargs.keys():
            raise_mismatch(
                fields,
                got=field_name,
                name="search filter field",
                mode="raise",
                comment="Check `include`, `exclude` or BaseUKF definition.",
            )

        _supported_includes = ["id", "kl", "filter", "sql"]
        include_set = set(include) if include is not None else {"id", "kl"}
        for inc in include_set:
            raise_mismatch(
                _supported_includes,
                got=inc,
                name="search `include` type",
                mode="warn",
                comment="It will be ignored in the return results.",
                thres=1.0,
            )

        facet = SQLCompiler.compile(orms=self.adapter.dims, expr=self.exprs, **kwargs)

        # When recoverable, use adapter.to_ukf (reads from main table)
        if self.recoverable and ("kl" in include_set):
            stmt = select(self.adapter.main)
            if facet is not None:
                stmt = stmt.where(facet)
            if orderby is not None:
                stmt = self._parse_orderby(stmt, orderby)
            if offset is not None:
                stmt = stmt.offset(offset)
            if topk is not None:
                stmt = stmt.limit(topk)
            with Session(self.db.engine) as session:
                results = list(session.execute(stmt).scalars())
                return [
                    {
                        "id": res.id,
                        **({"filter": facet} if "filter" in include_set else {}),
                        **({"sql": stmt.compile(bind=self.db.engine, compile_kwargs={"literal_binds": True})} if "sql" in include_set else {}),
                        **({"kl": self.adapter.to_ukf(entity=res)} if "kl" in include_set else {}),
                    }
                    for res in results
                ]
        else:
            stmt = select(self.adapter.main.id)
            if facet is not None:
                stmt = stmt.where(facet)
            if orderby is not None:
                stmt = self._parse_orderby(stmt, orderby)
            if offset is not None:
                stmt = stmt.offset(offset)
            if topk is not None:
                stmt = stmt.limit(topk)
            with Session(self.db.engine) as session:
                ids = list(session.scalars(stmt))
                return [
                    {
                        "id": ukf_id,
                        **({"filter": facet} if "filter" in include_set else {}),
                        **({"sql": stmt.compile(bind=self.db.engine, compile_kwargs={"literal_binds": True})} if "sql" in include_set else {}),
                    }
                    for ukf_id in ids
                ]

    def _search(
        self, topk: Optional[int] = None, offset: Optional[int] = None, include: Optional[Iterable[str]] = None, *args, **kwargs
    ) -> List[Dict[str, Any]]:
        """Alias for _search_facet for default search behavior."""
        return self._search_facet(topk=topk, offset=offset, include=include, *args, **kwargs)

    def _get(self, key: int, default: Any = ...) -> Optional[BaseUKF]:
        if not self.recoverable:
            return default
        return DatabaseKLStore._get(self, key, default=default)

    def _upsert(self, kl: BaseUKF, **kwargs):
        if self.inplace:
            return
        DatabaseKLStore._upsert(self, kl, **kwargs)

    def _insert(self, kl: BaseUKF, **kwargs):
        if self.inplace:
            return
        DatabaseKLStore._insert(self, kl, **kwargs)

    def _batch_upsert(self, kls, progress: Progress = None, **kwargs):
        if self.inplace:
            return
        DatabaseKLStore._batch_upsert(self, kls, progress=progress, **kwargs)

    def _batch_insert(self, kls, progress: Progress = None, **kwargs):
        if self.inplace:
            return
        DatabaseKLStore._batch_insert(self, kls, progress=progress, **kwargs)

    def _remove(self, key: int, **kwargs):
        if self.inplace:
            return
        DatabaseKLStore._remove(self, key, **kwargs)

    def _batch_remove(self, keys, progress: Progress = None, **kwargs):
        if self.inplace:
            return
        DatabaseKLStore._batch_remove(self, keys, progress=progress, **kwargs)

    def _clear(self):
        if self.inplace:
            return
        DatabaseKLStore._clear(self)

    def close(self):
        """\
        Closes the engine.
        """
        if self.db is not None:
            self.db.close()
        self.db = None
