__all__ = [
    "DatabaseKLStore",
]

from typing import Any, Generator, Optional, Iterable, Callable

from ..utils.basic.progress_utils import Progress
from sqlalchemy import delete, func as sqlalchemy_func, select, exists
from sqlalchemy.orm import Session

from ..utils.db import Database
from ..utils.basic.config_utils import HEAVEN_CM
from ..utils.basic.misc_utils import unique

from .base import BaseKLStore
from ..ukf.base import BaseUKF
from ..adapter.db import ORMUKFAdapter


class DatabaseKLStore(BaseKLStore):
    """\
    Database-backed KL store using the UKF ORM model.

    Minimal, clear implementation that maps UKF ORM rows to BaseUKF objects.
    """

    def __init__(self, database: Optional[str] = None, name: Optional[str] = None, condition: Optional[Callable] = None, *args, **kwargs):
        """\
        Initialize the database KL store.

        Args:
            database: Database name or path.
            name: Name of the KLStore instance. If None, defaults to "default".
            condition: Optional upsert/insert condition to apply to the KLStore.
                KLs that do not satisfy the condition will be ignored. If None, all KLs are accepted.
            *args: Additional positional arguments for BaseKLStore.
            **kwargs: Additional keyword arguments for BaseKLStore.
        """
        super().__init__(name=name or database, condition=condition, *args, **kwargs)
        provider = kwargs.get("provider") or HEAVEN_CM.get("db.default_provider")
        database = database or HEAVEN_CM.get(f"db.providers.{provider}.database")
        connection_args = {k: v for k, v in kwargs.items() if k not in ["database", "provider"]}

        self.db = Database(database=database, provider=provider, **connection_args)
        self.adapter = ORMUKFAdapter(name=self.name, include=None, exclude=None)
        self._init()

    def _init(self):
        for dim in self.adapter.dims.values():
            dim.metadata.create_all(self.db.engine)

    def _bulk_add_entities(self, session: Session, kls: list[BaseUKF]):
        """\
        Efficiently insert UKF entities using bulk_insert_mappings.

        This method replaces the inefficient add_all() approach with SQLAlchemy's
        bulk_insert_mappings(), which performs batch insertion in a single SQL statement
        for each table.

        Args:
            session: SQLAlchemy session to use for insertion.
            kls: List of BaseUKF objects to insert.
        """
        if not kls:
            return

        # Convert UKFs to dictionary mappings for bulk insertion
        mappings = self.adapter.entity_mappings(kls)

        # Insert main table first
        main_table_name = self.adapter.main.__tablename__
        if main_table_name in mappings and mappings[main_table_name]:
            session.bulk_insert_mappings(self.adapter.main, mappings[main_table_name])

        # Insert dimension tables
        for field_name, dim_cls in self.adapter.dims.items():
            if field_name == "main":
                continue
            table_name = dim_cls.__tablename__
            if table_name in mappings and mappings[table_name]:
                session.bulk_insert_mappings(dim_cls, mappings[table_name])

    def _remove_dim(self, session: Session, ukf_ids: Optional[Iterable[int]] = None):
        dim_clses = [dim for name, dim in self.adapter.dims.items() if name != "main"]
        if ukf_ids is None:
            for dim_cls in dim_clses:
                session.execute(delete(dim_cls))
            session.commit()  # DuckDB has strict FK constraints, so commit before main table delete is required
            return
        ukf_ids = list(ukf_ids)
        if not ukf_ids:
            return
        if len(ukf_ids) > 1:  # Efficiency consideration for single deletions
            for dim_cls in dim_clses:
                session.execute(delete(dim_cls).where(dim_cls.ukf_id.in_(ukf_ids)))
        else:
            for dim_cls in dim_clses:
                session.execute(delete(dim_cls).where(dim_cls.ukf_id == ukf_ids[0]))
        session.commit()  # DuckDB has strict FK constraints, so commit before main table delete is required

    def _has(self, key: int) -> bool:
        with Session(self.db.engine) as session:
            return bool(session.scalar(select(exists().where(self.adapter.main.id == key))))

    def _get(self, key: int, default: Any = ...) -> Optional[BaseUKF]:
        with Session(self.db.engine) as session:
            entity = session.get(self.adapter.main, key)
            return default if entity is None else self.adapter.to_ukf(entity=entity)

    def _batch_get(self, keys: list[int], default: Any = ...) -> list:
        if not keys:
            return []
        with Session(self.db.engine) as session:
            entities = {e.id: e for e in session.scalars(select(self.adapter.main).where(self.adapter.main.id.in_(keys)))}
            return [self.adapter.to_ukf(entity=entities[key]) if key in entities else default for key in keys]

    def _upsert(self, kl: BaseUKF, **kwargs):
        with Session(self.db.engine) as session:
            self._remove_dim(session, [kl.id])
            session.execute(delete(self.adapter.main).where(self.adapter.main.id == kl.id))
            self._bulk_add_entities(session, [kl])
            session.commit()

    def _batch_upsert(self, kls: list[BaseUKF], progress: Progress = None, **kwargs):
        kls = unique(kls, key=lambda kl: kl.id)  # Keeping only the first occurrence of each ID in case of duplicates
        if not kls:
            return
        with Session(self.db.engine) as session:
            ukf_ids = [kl.id for kl in kls]
            self._remove_dim(session, ukf_ids)
            session.execute(delete(self.adapter.main).where(self.adapter.main.id.in_(ukf_ids)))
            self._bulk_add_entities(session, kls)
            session.commit()
        if progress is not None:
            progress.update(len(kls))

    def _batch_insert(self, kls: list[BaseUKF], progress: Progress = None, **kwargs):
        kls = unique(kls, key=lambda kl: kl.id)  # Keeping only the first occurrence of each ID in case of duplicates
        if not kls:
            return
        with Session(self.db.engine) as session:
            ukf_ids = [kl.id for kl in kls]
            existing_ids = set(session.scalars(select(self.adapter.main.id).where(self.adapter.main.id.in_(ukf_ids))))
            delta_kls = [kl for kl in kls if kl.id not in existing_ids]
            if not delta_kls:
                return
            self._bulk_add_entities(session, delta_kls)
            session.commit()
        if progress is not None:
            progress.update(len(delta_kls))

    def _remove(self, key: int, **kwargs) -> bool:
        with Session(self.db.engine) as session:
            self._remove_dim(session, [key])
            result = session.execute(delete(self.adapter.main).where(self.adapter.main.id == key))
            session.commit()
            return result.rowcount > 0

    def _batch_remove(self, keys: Iterable[int], progress: Progress = None, **kwargs):
        keys = unique(keys)  # Keeping only unique keys
        if not keys:
            return
        with Session(self.db.engine) as session:
            self._remove_dim(session, keys)
            session.execute(delete(self.adapter.main).where(self.adapter.main.id.in_(keys)))
            session.commit()
        if progress is not None:
            progress.update(len(keys))
        return

    def __len__(self) -> int:
        with Session(self.db.engine) as session:
            return session.scalar(select(sqlalchemy_func.count()).select_from(self.adapter.main)) or 0

    def _itervalues(self) -> Generator[BaseUKF, None, None]:
        with Session(self.db.engine) as session:
            for main_entity in session.scalars(select(self.adapter.main)):
                yield self.adapter.to_ukf(entity=main_entity)

    def _clear(self):
        with Session(self.db.engine) as session:
            self._remove_dim(session, None)
            session.execute(delete(self.adapter.main))
            session.commit()

    def close(self):
        if self.db is not None:
            self.db.close()
        self.db = None
