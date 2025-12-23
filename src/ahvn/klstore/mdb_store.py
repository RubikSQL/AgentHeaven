__all__ = [
    "MongoKLStore",
]

from typing import Any, Generator, Optional, Iterable, Callable, List, Dict

from ..utils.basic.progress_utils import Progress

from ..utils.mdb import MongoDatabase
from ..utils.basic.config_utils import HEAVEN_CM
from ..utils.basic.misc_utils import unique

from .base import BaseKLStore
from ..ukf.base import BaseUKF
from ..adapter.mdb import MongoUKFAdapter


class MongoKLStore(BaseKLStore):
    """\
    MongoDB-backed KL store using the MongoUKFAdapter.

    Provides efficient CRUD operations for BaseUKF objects in MongoDB.
    Uses MongoDB's native operations for optimal performance.

    Note:
        This store handles only CRUD operations without vector embeddings.
        Vector search capabilities are provided by MongoKLEngine.
    """

    def __init__(
        self,
        database: Optional[str] = None,
        collection: Optional[str] = None,
        name: Optional[str] = None,
        condition: Optional[Callable] = None,
        include: Optional[list] = None,
        exclude: Optional[list] = None,
        *args,
        **kwargs,
    ):
        """\
        Initialize the MongoDB KL store.

        Args:
            database: MongoDB database name.
            collection: MongoDB collection name.
            name: Name of the KLStore instance. If None, defaults to collection name.
            condition: Optional upsert/insert condition to apply to the KLStore.
                KLs that do not satisfy the condition will be ignored. If None, all KLs are accepted.
            include: Optional list of fields to include in MongoDB documents.
            exclude: Optional list of fields to exclude from MongoDB documents.
            *args: Additional positional arguments for BaseKLStore.
            **kwargs: Additional keyword arguments for mongo database configuration.
        """
        super().__init__(name=name or collection, condition=condition, *args, **kwargs)
        database = database or kwargs.get("database") or HEAVEN_CM.get("mdb.database")
        collection = collection or kwargs.get("collection") or HEAVEN_CM.get("mdb.default_args.collection")
        connection_args = {
            k: v
            for k, v in kwargs.items()
            if k
            not in {
                "database",
                "collection",
                "include",
                "exclude",
            }
        }

        self.mdb = MongoDatabase(database=database, collection=collection, **connection_args)

        adapter_kwargs = {
            "name": self.name,
            "include": include,
            "exclude": exclude,
        }
        self.adapter = MongoUKFAdapter(**adapter_kwargs)
        self._init()

    def _init(self):
        """\
        Initialize collection and create indices.
        """
        self.mdb.connect()
        self.adapter.create_indices(self.mdb.conn)

    def _has(self, key: int) -> bool:
        """\
        Check if a document exists by ID.

        Args:
            key: The UKF ID to check.

        Returns:
            bool: True if document exists, False otherwise.
        """
        return self.mdb.conn.count_documents({"_id": self.adapter.parse_id(key)}, limit=1) > 0

    def _get(self, key: int, default: Any = ...) -> Optional[BaseUKF]:
        """\
        Retrieve a UKF by its ID.

        Args:
            key: The UKF ID to retrieve.
            default: Default value to return if not found.

        Returns:
            BaseUKF or default: The retrieved UKF or default value.
        """
        doc = self.mdb.conn.find_one({"_id": self.adapter.parse_id(key)})
        if doc is None:
            return default
        return self.adapter.to_ukf(doc)

    def _batch_get(self, keys: list[int], default: Any = ...) -> list:
        """\
        Retrieve multiple UKFs by their IDs efficiently.

        Args:
            keys: List of UKF IDs to retrieve.
            default: Default value to return if not found.

        Returns:
            list: List of retrieved UKFs or default values.
        """
        if not keys:
            return []
        ukf_ids = [self.adapter.parse_id(key) for key in keys]
        docs = {doc["_id"]: doc for doc in self.mdb.conn.find({"_id": {"$in": ukf_ids}})}
        return [self.adapter.to_ukf(docs[ukf_id]) if ukf_id in docs else default for ukf_id, key in zip(ukf_ids, keys)]

    def _batch_convert(self, kls: Iterable[BaseUKF]) -> List[Dict[str, Any]]:
        return [self.adapter.from_ukf(kl=kl, key=None, embedding=None) for kl in kls]

    def _upsert(self, kl: BaseUKF, **kwargs):
        """\
        Insert or update a UKF in the store.

        Args:
            kl: The UKF to upsert.
            **kwargs: Additional keyword arguments.
        """
        self.mdb.conn.replace_one(
            filter={"_id": self.adapter.parse_id(kl.id)},
            replacement=self.adapter.from_ukf(kl=kl, key=None, embedding=None),
            upsert=True,
        )

    def _batch_upsert(self, kls: list[BaseUKF], progress: Progress = None, **kwargs):
        """\
        Upsert multiple UKFs efficiently using bulk operations.

        Args:
            kls: List of UKFs to upsert.
            **kwargs: Additional keyword arguments.
        """
        kls = unique(kls, key=lambda kl: kl.id)
        if not kls:
            return
        from pymongo import ReplaceOne

        # Build bulk operations
        operations = [ReplaceOne(filter={"_id": doc["_id"]}, replacement=doc, upsert=True) for doc in self._batch_convert(kls)]
        if operations:
            self.mdb.conn.bulk_write(operations, ordered=False)
            if progress is not None:
                progress.update(len(kls))

    def _batch_insert(self, kls: list[BaseUKF], progress: Progress = None, **kwargs):
        """\
        Insert multiple UKFs efficiently, skipping existing ones.

        Args:
            kls: List of UKFs to insert.
            **kwargs: Additional keyword arguments.
        """
        kls = unique(kls, key=lambda kl: kl.id)
        if not kls:
            return
        ukf_ids = [self.adapter.parse_id(kl.id) for kl in kls]
        existing_ids = set(doc["_id"] for doc in self.mdb.conn.find({"_id": {"$in": ukf_ids}}))
        delta_kls = [kl for kl in kls if self.adapter.parse_id(kl.id) not in existing_ids]
        if not delta_kls:
            return
        self.mdb.conn.insert_many(self._batch_convert(delta_kls), ordered=False)
        if progress is not None:
            progress.update(len(delta_kls))

    def _remove(self, key: int, **kwargs) -> bool:
        """\
        Remove a UKF from the store by its ID.

        Args:
            key: The UKF ID to remove.
            **kwargs: Additional keyword arguments.

        Returns:
            bool: True if document was removed, False if not found.
        """
        return self.mdb.conn.delete_many({"_id": self.adapter.parse_id(key)}).deleted_count > 0

    def _batch_remove(self, keys: Iterable[int], progress: Progress = None, **kwargs):
        """\
        Remove multiple UKFs efficiently.

        Args:
            keys: Iterable of UKF IDs to remove.
            **kwargs: Additional keyword arguments.
        """
        keys = unique(keys)
        if not keys:
            return
        ukf_ids = [self.adapter.parse_id(key) for key in keys]
        result = self.mdb.conn.delete_many({"_id": {"$in": ukf_ids}})
        if progress is not None:
            progress.update(result.deleted_count or len(ukf_ids))

    def __len__(self) -> int:
        """\
        Get the number of documents in the store.

        Returns:
            int: Number of documents.
        """
        return self.mdb.conn.count_documents({})

    def _itervalues(self) -> Generator[BaseUKF, None, None]:
        """\
        Iterate over all UKFs in the store.

        Yields:
            BaseUKF: Each UKF in the store.
        """
        for doc in self.mdb.conn.find():
            yield self.adapter.to_ukf(doc)

    def _clear(self):
        """\
        Clear all documents from the store.
        """
        self.mdb.conn.delete_many({})

    def close(self):
        """\
        Close the MongoDB connection.
        """
        if self.mdb is not None:
            self.mdb.close()
        self.mdb = None

    def flush(self, **kwargs):
        """\
        Flush any pending operations (no-op for MongoDB as writes are immediate).
        """
        pass
