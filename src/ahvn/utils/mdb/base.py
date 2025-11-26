"""\
MongoDB connection wrapper for AgentHeaven.

This module provides a MongoDB connection class that follows the same pattern
as the Database class but uses PyMongo for MongoDB operations.
"""

from __future__ import annotations

__all__ = [
    "MongoDatabase",
]

from ..basic.log_utils import get_logger
from ..basic.debug_utils import error_str
from ..basic.request_utils import NetworkProxy
from ..basic.config_utils import HEAVEN_CM
from .mdb_utils import resolve_mdb_config
from ..deps import deps

from typing import Optional, List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from pymongo import MongoClient
    from pymongo.database import Database
    from pymongo.collection import Collection

logger = get_logger(__name__)

_pymongo = None


def get_pymongo():
    global _pymongo
    if _pymongo is None:
        _pymongo = deps.load("pymongo")
    return _pymongo


class MongoDatabase:
    """\
    MongoDB connection wrapper (PyMongo only, sync operations).

    Follows the same pattern as Database (utils/db/base.py):
    - Uses resolve_mdb_config() to get configuration from HEAVEN_CM
    - Handles connection string building with defaults
    - Manages connection lifecycle
    - Provides generic MongoDB access without UKF-specific logic

    Example:
        ```python
        # Use default config
        mongo = MongoDatabase()
        collection = mongo.conn

        # Override specific params
        mongo = MongoDatabase(host="192.168.1.100", port=27018)

        # Use connection string directly
        mongo = MongoDatabase(connection_string="mongodb://localhost:27017/mydb")

        # Context manager (auto-close)
        with MongoDatabase() as mongo:
            collection = mongo.mdb["test"]
            collection.insert_one({"name": "Alice"})
        ```

    Note:
        This class uses PyMongo for synchronous operations only.
        Motor (async) support will be added in a future phase.
    """

    def __init__(
        self,
        database: Optional[str] = None,
        collection: Optional[str] = None,
        connect: bool = False,
        **kwargs,
    ):
        """\
        Initialize MongoDB connection.

        Similar to Database.__init__(), resolves configuration from HEAVEN_CM.

        Args:
            database: Database name (optional, defaults to config value)
            collection: Collection name (optional, defaults to config value)
            connect: Whether to connect immediately upon initialization.
            **kwargs: Additional connection parameters that override config values
                - database: Database name (overrides config)
                - host: MongoDB host (overrides config)
                - port: MongoDB port (overrides config)
                - username: Auth username (overrides config)
                - password: Auth password (overrides config)
                - connection_string: Full connection string (overrides all)
                - maxPoolSize, connectTimeoutMS, etc.
        """
        self.config = resolve_mdb_config(database=database, collection=collection, **kwargs)
        self.database = self.config.pop("database", None)
        self.collection = self.config.pop("collection", None)
        self.proxy = NetworkProxy(
            http_proxy=self.config.pop("http_proxy", None),
            https_proxy=self.config.pop("https_proxy", None),
        )
        self._client = None
        if connect:
            self.connect()

    def connect(self):
        try:
            self._client = get_pymongo().MongoClient(**self.config)
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {error_str(e)}")
            raise

    def close(self):
        """\
        Close MongoDB connection and cleanup resources.
        """
        if self._client is not None:
            self._client.close()
        self._client = None

    @property
    def client(self) -> "MongoClient":
        """\
        Get PyMongo client for sync operations.

        Returns:
            MongoClient: The PyMongo client instance.
        """
        if self._client is None:
            raise ValueError("MongoDB client is not initialized")
        return self._client

    @property
    def mdb(self) -> "Database":
        """\
        Get the specified database collection.

        Returns:
            Database: The MongoDB database instance.
        """
        database = self.database or self.client.get_default_database().name
        return self.client[database]

    @property
    def conn(self) -> "Collection":
        """\
        Get the specified database collection.

        Returns:
            Collection: The MongoDB collection instance.
        """
        if not self._client:
            self.connect()
        database = self.database or self.client.get_default_database().name
        return self.client[database][self.collection]

    def create_index(self, keys: List[Tuple[str, int]], **kwargs):
        """\
        Create index on collection.

        Args:
            keys: List of (field, direction) tuples direction: 1 for ascending, -1 for descending
            **kwargs: Additional index options (unique, sparse, etc.)

        Example:
            >>> mongo.create_index([("name", 1)], name="users_name_idx")
            >>> mongo.create_index([("type", 1), ("age", -1)], name="users_type_age_idx", unique=True)
        """
        try:
            self.conn.create_index(keys, **kwargs)
            logger.debug(f"Created index on {self.conn.name}: {keys}")
        except Exception as e:
            logger.warning(f"Failed to create index on {self.conn.name}: {error_str(e)}")

    def create_vector_index(self, embedding_idx: str, embedding_field: str, dim: int):
        """\
        Create vector search index on collection.

        Args:
            embedding_idx: Name of the vector index to create.
            embedding_field: Field name containing the vector embeddings.
            dim: Dimensionality of the embedding vectors.

        Note:
            This only works with MongoDB Atlas, not local MongoDB instances.
        """
        try:
            existing_indices = list(self.conn.list_search_indexes())
            index_exists = any(idx.get("name") == embedding_idx for idx in existing_indices)
            if index_exists:
                logger.info(f"Vector index '{embedding_idx}' already exists on {self.conn.name}. Skipping creation.")
                return
            self.conn.create_search_index(
                model={
                    "name": embedding_idx,
                    "type": "vectorSearch",
                    "definition": {
                        "fields": [
                            {
                                **HEAVEN_CM.get("mdb.vector_index", dict()),
                                "path": embedding_field,
                                "numDimensions": dim,
                            }
                        ]
                    },
                }
            )
        except Exception as e:
            logger.warning(f"Could not create vector index (expected for non-Atlas MongoDB): {e}")

    def __enter__(self):
        """\
        Context manager entry: returns self.
        """
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """\
        Context manager exit: closes connection.
        """
        self.close()
        return False
