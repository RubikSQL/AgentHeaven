"""\
MongoDB-based cache backend.
"""

__all__ = [
    "MongoCache",
]

from .base import BaseCache
from typing import Any, Generator, Optional, Iterable, Dict

from ..utils.basic.debug_utils import DatabaseError
from ..utils.basic.hash_utils import fmt_hash
from ..utils.basic.serialize_utils import dumps_json, loads_json
from ..utils.mdb.base import MongoDatabase


class MongoCache(BaseCache):
    """\
    An implementation of BaseCache that stores data in a MongoDB collection.
    Each cache entry is stored as a document with an integer _id (cache key) and a content field (JSON data).
    """

    def __init__(
        self,
        database: Optional[str] = None,
        collection: Optional[str] = None,
        exclude: Optional[Iterable[str]] = None,
        *args,
        **kwargs,
    ):
        """\
        Initialization.

        Args:
            database (Optional[str]): MongoDB database name.
            collection (Optional[str]): MongoDB collection name for cache storage.
            exclude (Optional[Iterable[str]]): Keys to exclude from inputs when creating cache entries.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments for MongoDB connection.
        """
        super().__init__(exclude=exclude, *args, **kwargs)
        self._mdb = MongoDatabase(database=database, collection=collection, **kwargs)
        self._create()

    def _create(self):
        """\
        Initialize MongoDB collection and create index on _id if needed.
        """
        self._mdb.connect()
        # Create index on _id for faster lookups (though _id is indexed by default)
        # We can add additional indices here if needed in the future

    def _has(self, key: int) -> bool:
        """\
        Check if a cache entry exists for the given key.

        Args:
            key (int): The cache key to check.

        Returns:
            bool: True if the entry exists, False otherwise.
        """
        # Use fmt_hash to convert key to string representation
        return self._mdb.conn.count_documents({"_id": fmt_hash(key)}, limit=1) > 0

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
        # Use fmt_hash to convert key to string representation
        result = list(self._mdb.conn.find({"_id": fmt_hash(key)}))
        if len(result) < 1:
            return default
        if len(result) > 1:
            raise DatabaseError(f"Multiple cache entries found, please check your MongoCache consistency. Id: {key}.")
        content = result[0].get("content")
        # Deserialize using loads_json which handles AhvnJsonEncoder
        if content:
            content = loads_json(content)
        return content

    def _set(self, key: int, value: Dict[str, Any]):
        """\
        Set a cache entry for the given key.

        Args:
            key (int): The cache key to set.
            value (Dict[str, Any]): The data to cache.
        """
        # Use fmt_hash to convert key to string representation
        # Use dumps_json to serialize value with AhvnJsonEncoder
        serialized_value = dumps_json(value)
        self._mdb.conn.update_one({"_id": fmt_hash(key)}, {"$set": {"content": serialized_value}}, upsert=True)

    def _remove(self, key: int):
        """\
        Remove a cache entry by its key.

        Args:
            key (int): The cache key to remove.
        """
        # Use fmt_hash to convert key to string representation
        self._mdb.conn.delete_one({"_id": fmt_hash(key)})

    def __len__(self) -> int:
        """\
        Get the number of cache entries.

        Returns:
            int: The number of entries in the cache.
        """
        return self._mdb.conn.count_documents({})

    def _itervalues(self) -> Generator[Dict[str, Any], None, None]:
        """\
        Iterate over all cache entry values.

        Yields:
            Dict[str, Any]: Each cached data entry.
        """
        for document in self._mdb.conn.find({}):
            content = document.get("content")
            if content is not None:
                yield loads_json(content)

    def _clear(self):
        """\
        Clear all cache entries.
        """
        self._mdb.conn.delete_many({})

    def close(self):
        """\
        Close the MongoDB connection.
        """
        if self._mdb is not None:
            self._mdb.close()
        self._mdb = None
