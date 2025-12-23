"""\
Database-based cache backend.
"""

__all__ = [
    "DatabaseCache",
]

from .base import BaseCache
from typing import Any, Generator, Optional, Iterable, Dict

from ..utils.basic.debug_utils import DatabaseError

from ..utils.db.base import Database
from ..utils.db.types import ExportableEntity, DatabaseIdType, DatabaseJsonType
from sqlalchemy import Column, Index


class CacheORMEntity(ExportableEntity):
    """\
    Simple cache table for storing key-value pairs with JSON content.
    """

    __tablename__ = "cache_orm"

    id = Column(DatabaseIdType(), primary_key=True)
    content = Column(DatabaseJsonType(), nullable=True)

    __table_args__ = (Index("idx_cache_id", "id"), {"extend_existing": True})


class DatabaseCache(BaseCache):
    """\
    An implementation of BaseCache that stores data in a database table using JSON columns.
    Each cache entry is stored as a row with a string key and JSON data using the CacheORMEntity model.
    """

    def __init__(self, provider: str = None, database: str = None, exclude: Optional[Iterable[str]] = None, *args, **kwargs):
        """\
        Initialization.

        Args:
            provider (str): Database provider ('sqlite', 'pg', 'duckdb', etc.).
            database (str): Database name or path (':memory:' for in-memory).
            exclude (Optional[Iterable[str]]): Keys to exclude from inputs when creating cache entries.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments for database connection.
        """
        super().__init__(exclude=exclude, *args, **kwargs)
        self._db = Database(provider=provider, database=database, **kwargs)
        self._create()

    def _create(self):
        """\
        Create the cache table if it doesn't exist using SQLAlchemy.
        """
        # CacheORMEntity.metadata.create_all(self._db.engine, tables=[CacheORMEntity.__table__], checkfirst=True)
        with self._db:
            for stmt in CacheORMEntity.create_stmts():
                self._db.orm_execute(stmt)

    def _has(self, key: int) -> bool:
        """\
        Check if a cache entry exists for the given key.

        Args:
            key (int): The cache key to check.

        Returns:
            bool: True if the entry exists, False otherwise.

        Raises:
            DatabaseError: If the existence is not correctly returned from SQL.
        """
        stmt = CacheORMEntity.exists_stmt(key)
        result = self._db.orm_execute(stmt).to_list(row_fmt="tuple")
        if len(result) != 1:
            raise DatabaseError("Unexpected result format when checking cache entry existence.")
        if len(result[0]) != 1:
            raise DatabaseError("Unexpected result format when checking cache entry existence.")
        return bool(result[0][0])

    def _get(self, key: int, default: Any = ...) -> Dict[str, Any]:
        """\
        Retrieve a cache entry by its key.

        Args:
            key (int): The cache key to retrieve.
            default (Any): The default value to return if not found.

        Returns:
            Dict[str, Any]: The cached data if found, otherwise default.

        Raises:
            DatabaseError: If multiple cache entries are found.
        """
        stmt = CacheORMEntity.get_stmt(key)
        result = self._db.orm_execute(stmt).to_list(row_fmt="dict")
        if len(result) < 1:
            return default
        if len(result) > 1:
            raise DatabaseError(f"Multiple cache entries found, please check your DatabaseCache consistency. Id: {key}.")
        content = result[0].get("content")
        return content

    def _set(self, key: int, value: Dict[str, Any]):
        """\
        Set a cache entry for the given key.

        Args:
            key (int): The cache key to set.
            value (Dict[str, Any]): The data to cache.
        """
        stmts = CacheORMEntity(id=key, content=value).upsert_stmts()
        for stmt in stmts:
            self._db.orm_execute(stmt, autocommit=True)

    def _remove(self, key: int):
        """\
        Remove a cache entry by its key.

        Args:
            key (int): The cache key to remove.
        """
        stmts = CacheORMEntity.remove_stmts(id=key)
        for stmt in stmts:
            self._db.orm_execute(stmt, autocommit=True)

    def __len__(self) -> int:
        """\
        Get the number of cache entries.

        Returns:
            int: The number of entries in the cache.

        Raises:
            DatabaseError: If the count is not correctly returned from SQL.
        """
        from sqlalchemy import select, func

        table = CacheORMEntity.__table__
        stmt = select(func.count()).select_from(table)
        result = self._db.orm_execute(stmt).to_list(row_fmt="tuple")
        if len(result) != 1:
            raise DatabaseError("Unexpected result format when counting cache entries.")
        if len(result[0]) != 1:
            raise DatabaseError("Unexpected result format when counting cache entries.")
        return int(result[0][0])

    def _itervalues(self) -> Generator[Dict[str, Any], None, None]:
        """\
        Iterate over all cache entry values.

        Yields:
            Dict[str, Any]: Each cached data entry.
        """
        from sqlalchemy import select

        table = CacheORMEntity.__table__
        stmt = select(table.c.content)
        result = self._db.orm_execute(stmt).to_list(row_fmt="dict")
        for record in result:
            content = record.get("content")
            yield content
        return

    def _clear(self):
        """\
        Clear all cache entries.
        """
        from sqlalchemy import delete

        table = CacheORMEntity.__table__
        stmt = delete(table)
        self._db.orm_execute(stmt, autocommit=True)

    def close(self):
        """\
        Close the database connection.
        """
        if self._db is not None:
            self._db.close()
        self._db = None
