"""MongoDB-based KL engine implementation."""

__all__ = [
    "MongoKLEngine",
]

from typing import Any, Dict, Iterable, List, Tuple, Optional, Callable

from ..utils.mdb import MongoDatabase
from ..utils.mdb.compiler import MongoCompiler
from ..utils.basic.log_utils import get_logger
from ..utils.basic.config_utils import HEAVEN_CM
from ..utils.basic.debug_utils import raise_mismatch
from ..utils.basic.hash_utils import fmt_hash
from ..utils.basic.misc_utils import unique
from ..utils.basic.progress_utils import Progress
from ..utils.klop import KLOp
from ..utils.vdb.vdb_utils import parse_encoder_embedder
from ..klstore.base import BaseKLStore
from ..klstore.mdb_store import MongoKLStore
from ..adapter.mdb import MongoUKFAdapter

logger = get_logger(__name__)

from .base import BaseKLEngine
from ..ukf.base import BaseUKF


class MongoKLEngine(BaseKLEngine):
    """\
    A MongoDB-based search KLEngine implementation that provides multiple search interfaces.

    This class extends BaseKLEngine with specialized search methods:
    - MongoDB query language (MQL) search through _search_mql method
    - Vector similarity + filter hybrid search through _search_vector method (requires encoder/embedder)
    - Default search delegates to vector search

    The engine supports two modes:
    - inplace=True: Search directly on storage MongoDB collection (storage must be MongoKLStore)
    - inplace=False: Create separate MongoDB collection for indexing with custom field selection

    Vector Search Support:
    - Requires encoder and embedder to be configured
    - Uses MongoDB's $vectorSearch for efficient similarity search
    - Combines vector search with MQL filters for hybrid retrieval

    Search Methods:
        _search_mql(mql, include, *args, **kwargs): Raw MQL query search.
        _search_vector(query, topk, fetchk, include, **kwargs): Execute hybrid vector + filter search.
        _search = _search_vector: Alias for _search_vector for default search behavior.

    Abstract Methods (inherited from BaseKLEngine):
        _upsert(kl): Insert or update a KL in the engine.
        _remove(key): Remove a KL from the engine by its key (id).
        _clear(): Clear all KLs from the engine.
    """

    inplace: bool = True
    recoverable: bool = True

    def __init__(
        self,
        storage: "BaseKLStore",
        inplace: bool = True,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        filters: Optional[dict] = None,
        name: Optional[str] = None,
        condition: Optional[Callable] = None,
        encoder: Optional[Callable] = None,
        embedder: Optional[Callable] = False,
        *args,
        **kwargs,
    ):
        """Initialize the MongoKLEngine.

        Args:
            storage: Attach MongoKLEngine to a KLStore.
                For inplace=True, must be a MongoKLStore instance.
                For inplace=False, can be any KLStore.
            inplace: If True, search directly on storage MongoDB collection;
                if False, create a separate MongoDB collection for indexing.
            include (if inplace=False): List of BaseUKF field names to include.
                If None, includes all fields. Default is None.
            exclude (if inplace=False): List of BaseUKF field names to exclude.
                If None, excludes no fields. Default is None.
                Notice that exclude is applied after include, so if a field is in both,
                it will be excluded. It is recommended to use only one of include or exclude.
            filters: Global filters that will be applied to all searches.
            name: Name of the KLEngine instance.
                If None, defaults to "{storage.name}_mongo_idx" for non-inplace mode.
            condition: Optional upsert/insert condition to apply to the KLEngine.
                KLs that do not satisfy the condition will be ignored. If None, all KLs are accepted.
            encoder: Optional encoder function for converting queries/KLs to text.
                If None, a default provider will be used.
            embedder: Optional embedder function for converting encoded text to vectors.
                If False, vector search is not available.
                If None, a default embedder will be used.
            *args: Additional positional arguments passed to MongoKLEngine.
            **kwargs: Additional keyword arguments passed to MongoKLEngine.
        """
        if inplace and not isinstance(storage, MongoKLStore):
            raise ValueError("When inplace=True, storage must be a MongoKLStore instance")

        super().__init__(storage=storage, inplace=inplace, name=name or f"{storage.name}_mongo_idx", condition=condition, *args, **kwargs)
        self.exprs = None if not filters else KLOp.expr(**filters)

        (self.k_encoder, self.q_encoder), (self.k_embedder, self.q_embedder), self.k_dim, self.q_dim = parse_encoder_embedder(
            encoder=encoder,
            embedder=embedder,
        )
        # Only enable vector search if encoder AND embedder were explicitly provided
        self._has_vector = (encoder is not None) and encoder and (embedder is not None) and embedder

        if self.inplace:
            self.mdb = self.storage.mdb
            self.adapter = self.storage.adapter
        else:
            database = kwargs.get("database") or HEAVEN_CM.get("mdb.default_args.database")
            collection = kwargs.get("collection") or self.name or HEAVEN_CM.get("mdb.default_args.collection")
            connection_args = {k: v for k, v in kwargs.items() if k not in ["database", "collection", "encoder", "embedder", "include", "exclude"]}
            self.mdb = MongoDatabase(database=database, collection=collection, **connection_args)
            self.mdb.connect()
            self.adapter = MongoUKFAdapter(name=self.name, include=include, exclude=exclude)
            self._init()

        self.recoverable = self.adapter.recoverable

    def k_encode(self, kl: Any) -> str:
        """Encode a KL object to text using k_encoder."""
        if not self._has_vector:
            return None
        return self.k_encoder(kl)

    def k_embed(self, encoded_kl: str) -> List[float]:
        """Generate embedding from encoded KL text using k_embedder."""
        if not self._has_vector:
            return None
        return self.k_embedder(encoded_kl)

    def batch_k_encode(self, kls: Iterable[Any]) -> List[str]:
        """Batch encode KL objects to text using k_encoder."""
        if not len(kls):
            return list()
        if not self._has_vector:
            return [None] * len(kls)
        return [self.k_encoder(kl) for kl in kls]

    def batch_k_embed(self, encoded_kls: List[str]) -> List[List[float]]:
        """Batch generate embeddings from encoded KL texts using k_embedder."""
        if not len(encoded_kls):
            return list()
        if not self._has_vector:
            return [None] * len(encoded_kls)
        return self.k_embedder(encoded_kls)

    def q_encode(self, query: Any) -> str:
        """Encode a query to text using q_encoder."""
        return self.q_encoder(query)

    def batch_q_encode(self, queries: Iterable[Any]) -> List[str]:
        """Batch encode queries to text using q_encoder."""
        if not len(queries):
            return list()
        return [self.q_encoder(query) for query in queries]

    def q_embed(self, encoded_query: str) -> List[float]:
        """Generate embedding from encoded query text using q_embedder."""
        return self.q_embedder(encoded_query)

    def batch_q_embed(self, encoded_queries: List[str]) -> List[List[float]]:
        """Batch generate embeddings from encoded query texts using q_embedder."""
        if not len(encoded_queries):
            return list()
        return self.q_embedder(encoded_queries)

    def k_encode_embed(self, obj: Any) -> Tuple[str, List[float]]:
        """Encode an object and generate its embedding.

        Args:
            obj: Object to encode and embed.

        Returns:
            Tuple of (encoded_text, embedding).
        """
        if not self._has_vector:
            return None, None
        encoded_text = self.k_encode(obj)
        embedding = self.k_embed(encoded_text)
        return encoded_text, embedding

    def batch_k_encode_embed(self, objs: Iterable[Any]) -> List[Tuple[str, List[float]]]:
        """Batch encode objects and generate their embeddings.

        Args:
            objs: Iterable of objects to encode and embed.

        Returns:
            List of tuples (encoded_text, embedding) for each object.
        """
        if not len(objs):
            return list()
        if not self._has_vector:
            return [(None, None)] * len(objs)
        k_encoded_texts = self.batch_k_encode(objs)
        k_embeddings = self.batch_k_embed(k_encoded_texts)
        return list(zip(k_encoded_texts, k_embeddings))

    def q_encode_embed(self, query: Any) -> Tuple[str, List[float]]:
        """Encode a query and generate its embedding.

        Args:
            query: Query to encode and embed.

        Returns:
            Tuple of (encoded_text, embedding).
        """
        encoded_text = self.q_encode(query)
        embedding = self.q_embed(encoded_text)
        return encoded_text, embedding

    def batch_q_encode_embed(self, queries: Iterable[Any]) -> List[Tuple[str, List[float]]]:
        """Batch encode queries and generate their embeddings.

        Args:
            queries: Iterable of queries to encode and embed.

        Returns:
            List of tuples (encoded_text, embedding) for each query.
        """
        if not len(queries):
            return list()
        q_encoded_texts = self.batch_q_encode(queries)
        q_embeddings = self.batch_q_embed(q_encoded_texts)
        return list(zip(q_encoded_texts, q_embeddings))

    def _init(self):
        """Initialize the engine: create indices and sync from storage if needed."""
        self.mdb.connect()
        self.adapter.create_indices(self.mdb.conn)
        if self._has_vector:
            self.adapter.create_vector_index(self.mdb.conn, dim=self.k_dim)

    def _batch_convert(self, kls: Iterable[BaseUKF]) -> List[Dict[str, Any]]:
        """Convert a batch of KLs to MongoDB documents with embeddings.

        Args:
            kls: Iterable of KLs to convert.

        Returns:
            List of MongoDB documents.
        """
        documents = []
        keys_embeddings = self.batch_k_encode_embed(kls)
        for kl, (key, embedding) in zip(kls, keys_embeddings):
            doc = self.adapter.from_ukf(kl=kl, key=key, embedding=embedding)
            documents.append(doc)
        return documents

    def _get(self, key: int, default: Any = ...) -> Optional[BaseUKF]:
        if not self.recoverable:
            return default
        return MongoKLStore._get(self, key, default=default)

    def _has(self, key: int) -> bool:
        if self._has_vector:
            return (
                self.mdb.conn.count_documents(
                    {
                        "_id": fmt_hash(key),
                        "$or": [{self.adapter.embedding_field: {"$exists": True}}, {self.adapter.embedding_field: None}],
                    },
                    limit=1,
                )
                > 0
            )
        return MongoKLStore._has(self, key)

    def __len__(self) -> int:
        if self._has_vector:
            return self.mdb.conn.count_documents({"$or": [{self.adapter.embedding_field: {"$exists": True}}, {self.adapter.embedding_field: None}]})
        if self.inplace:
            return len(self.storage)
        return len(self.mdb.conn.count_documents({}))

    def _upsert(self, kl: BaseUKF, **kwargs):
        """\
        Insert or update a KL in the engine.

        - If inplace=True: Only update vector to the existing data record in storage, do not modify other fields.
        - If inplace=False: Upsert kl to the engine's collection.

        Args:
            kl: The KL to upsert.
            kwargs: Additional keyword arguments.
        """
        if self.inplace:
            if not self._has_vector:
                return
            if not self._has(kl.id):
                return
            key, embedding = self.k_encode_embed(kl)
            self.mdb.conn.update_one(
                filter={"_id": self.adapter.parse_id(kl.id)},
                update={
                    "$set": {
                        self.adapter.key_field: key,
                        self.adapter.embedding_field: embedding,
                    }
                },
                upsert=False,
            )
        else:
            MongoKLStore._upsert(self, kl, **kwargs)

    def _insert(self, kl: BaseUKF, **kwargs):
        """\
        Insert a KL in the engine.

        - If inplace=True: Only update vector to the existing data record in storage, do not modify other fields.
        - If inplace=False: Insert kl to the engine's collection.

        Args:
            kl: The KL to insert.
            kwargs: Additional keyword arguments.
        """
        if self.inplace:
            if not self._has_vector:
                return
            if self._has(kl.id):
                return
            original_kl = self._get(kl.id)
            key, embedding = self.k_encode_embed(original_kl)
            self.mdb.conn.update_one(
                filter={"_id": self.adapter.parse_id(kl.id)},
                update={
                    "$set": {
                        self.adapter.key_field: key,
                        self.adapter.embedding_field: embedding,
                    }
                },
                upsert=False,
            )
        else:
            MongoKLStore._insert(self, kl, **kwargs)

    def _batch_upsert(self, kls, progress: Progress = None, **kwargs):
        """\
        Batch upsert KLs in the engine.

        - If inplace=True: Only update vector to the existing data record in storage, do not modify other fields.
        - If inplace=False: Upsert kl to the engine's collection.

        Args:
            kls: Iterable of KLs to upsert.
            kwargs: Additional keyword arguments.
        """
        if self.inplace:
            if not self._has_vector:
                return
            kls = unique(kls, key=lambda kl: kl.id)
            kls = [kl for kl in kls if self._has(kl.id)]
            if not kls:
                return
            operations = []
            keys_embeddings = self.batch_k_encode_embed(kls)
            from pymongo import UpdateOne

            for kl, (key, embedding) in zip(kls, keys_embeddings):
                operations.append(
                    UpdateOne(
                        filter={"_id": self.adapter.parse_id(kl.id)},
                        update={
                            "$set": {
                                self.adapter.key_field: key,
                                self.adapter.embedding_field: embedding,
                            }
                        },
                        upsert=False,
                    )
                )
            if operations:
                result = self.mdb.conn.bulk_write(operations, ordered=False)
                if progress is not None:
                    progress.update(result.bulk_api_result.get("nModified", len(kls)))
        else:
            MongoKLStore._batch_upsert(self, kls, progress=progress, **kwargs)

    def _batch_insert(self, kls, progress: Progress = None, **kwargs):
        """\
        Batch insert KLs in the engine.

        - If inplace=True: Only update vector to the existing data record in storage, do not modify other fields.
        - If inplace=False: Insert kl to the engine's collection.

        Args:
            kls: Iterable of KLs to insert.
        """
        if self.inplace:
            if not self._has_vector:
                return
            kls = unique(kls, key=lambda kl: kl.id)
            kls = [kl for kl in kls if not self._has(kl.id)]
            if not kls:
                return
            operations = []
            original_kls = [self._get(kl.id) for kl in kls]
            key_embeddings = self.batch_k_encode_embed(original_kls)
            from pymongo import ReplaceOne

            for original_kl, (key, embedding) in zip(original_kls, key_embeddings):
                operations.append(
                    ReplaceOne(
                        filter={"_id": self.adapter.parse_id(original_kl.id)},
                        replacement={
                            "$set": {
                                self.adapter.key_field: key,
                                self.adapter.embedding_field: embedding,
                            }
                        },
                        upsert=False,
                    )
                )
            if operations:
                result = self.mdb.conn.bulk_write(operations, ordered=False)
                if progress is not None:
                    progress.update(result.bulk_api_result.get("nInserted", len(kls)))
        else:
            MongoKLStore._batch_insert(self, kls, progress=progress, **kwargs)

    def _remove(self, key: int, **kwargs):
        """\
        Remove a KL from the engine.

        - If inplace=True: Only clear vector field from the existing data record in storage.
        - If inplace=False: Remove kl from the engine's collection.

        Args:
            key: The key (id) of the KL to remove.
            kwargs: Additional keyword arguments.
        """
        if self.inplace:
            if not self._has_vector:
                return
            if not self._has(key):
                return
            self.mdb.conn.update_one(
                filter={"_id": self.adapter.parse_id(key)},
                update={
                    "$unset": {
                        self.adapter.key_field: "",
                        self.adapter.embedding_field: "",
                    }
                },
                upsert=False,
            )
        else:
            MongoKLStore._remove(self, key, **kwargs)

    def _batch_remove(self, keys, progress: Progress = None, **kwargs):
        """\
        Batch remove KLs from the engine.

        - If inplace=True: Only clear vector field from the existing data record in storage.
        - If inplace=False: Remove kl from the engine's collection.

        Args:
            keys: Iterable of keys (ids) of KLs to remove.
            kwargs: Additional keyword arguments.
        """
        if self.inplace:
            if not self._has_vector:
                return
            keys = unique(keys)
            keys = [key for key in keys if self._has(key)]
            if not keys:
                return
            ukf_ids = [self.adapter.parse_id(key) for key in keys]
            result = self.mdb.conn.update_many(
                filter={"_id": {"$in": ukf_ids}},
                update={
                    "$unset": {
                        self.adapter.key_field: "",
                        self.adapter.embedding_field: "",
                    }
                },
                upsert=False,
            )
            if progress is not None:
                progress.update(result.modified_count or len(ukf_ids))
        else:
            MongoKLStore._batch_remove(self, keys, progress=progress, **kwargs)

    def _clear(self):
        """\
        Clear all KLs from the engine.

        - If inplace=True: Only clear all vector fields from existing data records in storage.
        - If inplace=False: Clear all KLs from the engine's collection.
        """
        if self.inplace:
            if not self._has_vector:
                return
            self.mdb.conn.update_many(
                filter={"$or": [{self.adapter.embedding_field: {"$exists": True}}, {self.adapter.embedding_field: None}]},
                update={
                    "$unset": {
                        self.adapter.key_field: "",
                        self.adapter.embedding_field: "",
                    }
                },
                upsert=False,
            )
        else:
            MongoKLStore._clear(self)

    def _parse_orderby(self, orderby: Iterable[str]) -> Dict[str, int]:
        sort_stage = {}
        fields = set(self.adapter.fields)
        for field in orderby:
            desc = field.startswith("-")
            field_name = field[1:] if desc else field

            raise_mismatch(
                fields,
                got=field_name,
                name="orderby field",
                mode="raise",
                comment="Check `include`, `exclude` or BaseUKF definition.",
            )

            sort_stage[field_name] = -1 if desc else 1
        return sort_stage

    def _search_vector(
        self,
        query: str = None,
        topk: int = -1,
        fetchk: Optional[int] = -1,
        orderby: Optional[Iterable[str]] = None,
        include: Optional[Iterable[str]] = None,
        *args,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """\
        Perform a hybrid vector similarity + filter search on MongoDB.

        This method combines vector similarity search with MongoDB filters for powerful
        hybrid retrieval combining semantic search and structured filtering.

        Args:
            query (str): The text query to search for using vector similarity.
                If None, only filter-based search is performed without vector search.
            topk (int): Number of top results to return. Default is -1, meaning no limit.
                Notice that when query is provided, topk is applied after vector search and filtering.
                Vector search fetches up to fetchk candidates, which are then filtered and reranked to return topk results.
                MongoDB vector search requires 0 < topk <= 10000, capping topk to 10000 if exceeded.
            fetchk (Optional[int]): Number of candidates to fetch for reranking.
                If None, uses self.fetchk. The effective value is max(fetchk, topk, 0). Default is -1, meaning no limit.
                MongoDB vector search requires 0 < fetchk <= 10000, capping fetchk to 10000 if exceeded.
            include (Optional[Iterable[str]]): The keys to include in the search results.
                Supported keys include:
                - 'id': The unique identifier of the KL (BaseUKF.id).
                - 'kl': The KL object itself (BaseUKF).
                - 'score': The similarity score from vector search.
                - 'filter': The IR-level filter expression (KLOp.expr format).
                - 'mql': The compiled MongoDB filter for debugging.
                Defaults to None, which resolves to ['id', 'kl', 'score'].
            *args: Additional positional arguments.
            **kwargs: Filter conditions as keyword arguments.

        Returns:
            List[Dict[str, Any]]: The search results matching the applied filters and query.

        Raises:
            ValueError: If encoder/embedder not configured (when query is not None) or filter fields not in schema.
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

        _supported_includes = ["id", "kl", "score", "filter", "mql", "key", "embedding", "qkey", "qembedding"]
        include_set = set(include) if include is not None else {"id", "kl", "score"}
        for inc in include_set:
            raise_mismatch(
                _supported_includes,
                got=inc,
                name="search `include` type",
                mode="warn",
                comment="It will be ignored in the return results.",
                thres=1.0,
            )

        # Build metadata filters
        mql_filters = MongoCompiler.compile(expr=self.exprs, **kwargs)
        if query is None:
            query_key, query_embedding = None, None
        else:
            query_key, query_embedding = self.q_encode_embed(query)

        # Build MongoDB aggregation pipeline
        query_pipeline = []
        # If query is provided, add vector search stage
        if query_embedding is not None:
            fetchk = max(fetchk or topk, topk, 0)
            if fetchk > 10000 or fetchk <= 0:
                logger.warning("MongoDB vector search requires `numCandidates` <= 10000, capping `fetchk` to 10000.")
                fetchk = 10000
            if topk > 10000 or topk <= 0:
                logger.warning("MongoDB vector search requires `limit` <= 10000, capping `topk` to 10000.")
                topk = 10000
            query_pipeline.append(
                {
                    "$vectorSearch": {
                        "index": self.adapter.embedding_idx,
                        "path": self.adapter.embedding_field,
                        "queryVector": query_embedding,
                        "numCandidates": fetchk,
                        "limit": topk,
                    }
                }
            )
            query_pipeline.append({"$addFields": {"score": {"$meta": "vectorSearchScore"}}})
        if mql_filters:
            query_pipeline.append({"$match": mql_filters})
        if orderby is not None:
            sort_stage = self._parse_orderby(orderby)
            if sort_stage:
                query_pipeline.append({"$sort": sort_stage})
        if topk > 0:
            query_pipeline.append({"$limit": topk})
        try:
            results = list(self.mdb.conn.aggregate(query_pipeline))
        except Exception as e:
            logger.error(f"Error during vector search aggregation: {e}")
            return list()

        return [
            {
                "id": int(doc["_id"]),
                **({"score": float(doc.get("score", 0.0))} if "score" in include_set else {}),
                **({"filter": mql_filters} if "filter" in include_set else {}),
                **({"mql": query_pipeline} if "mql" in include_set else {}),
                **({"key": doc.get(self.adapter.key_field)} if "key" in include_set else {}),
                **({"embedding": doc.get(self.adapter.embedding_field)} if "embedding" in include_set else {}),
                **({"qkey": query_key} if "qkey" in include_set else {}),
                **({"qembedding": query_embedding} if "qembedding" in include_set else {}),
                **({"kl": BaseUKF.from_dict(self.adapter.to_ukf_data(doc), polymorphic=True)} if "kl" in include_set else {}),
            }
            for doc in results
        ]

    def _search(
        self,
        query: str = None,
        topk: int = -1,
        fetchk: Optional[int] = -1,
        orderby: Optional[Iterable[str]] = None,
        include: Optional[Iterable[str]] = None,
        *args,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """Alias for _search_vector for default search behavior."""
        return self._search_vector(query=query, topk=topk, fetchk=fetchk, orderby=orderby, include=include, *args, **kwargs)

    def _search_mql(
        self, mql: Dict[str, Any], orderby: Optional[Iterable[str]] = None, include: Optional[Iterable[str]] = None, *args, **kwargs
    ) -> List[Dict[str, Any]]:
        """\
        Perform a raw MongoDB Query Language (MQL) search.

        This method allows direct execution of MongoDB queries for advanced users
        who need full control over the query structure. Global filters (self.exprs)
        are automatically combined with the provided MQL.

        Args:
            mql (Dict[str, Any]): Raw MongoDB query dict.
                Example: {"type": "person", "age": {"$gt": 18}}
            orderby (Optional[Iterable[str]]): List of fields to order the results by.
                Each field can be prefixed with '-' for descending order. Defaults to None (no specific order).
            include (Optional[Iterable[str]]): The keys to include in the search results.
                Supported keys include:
                - 'id': The unique identifier of the KL (BaseUKF.id).
                - 'kl': The KL object itself (BaseUKF).
                - 'mql': The combined MQL query (global + provided) for debugging.
                Defaults to None, which resolves to ['id', 'kl'].
            *args: Additional positional arguments (not used).
            **kwargs: Additional keyword arguments (not used).

        Returns:
            List[Dict[str, Any]]: The search results matching the MQL query.
        """
        _supported_includes = ["id", "kl", "mql"]
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
        # Wrap the MQL filter in a $match stage for aggregation pipeline
        pipeline = [{"$match": mql}] if mql else []
        if orderby is not None:
            sort_stage = self._parse_orderby(orderby)
            if sort_stage:
                pipeline.append({"$sort": sort_stage})
        results = self.mdb.conn.aggregate(pipeline)
        return [
            {
                "id": int(doc["_id"]),
                **({"mql": mql} if "mql" in include_set else {}),
                **({"kl": BaseUKF.from_dict(self.adapter.to_ukf_data(doc), polymorphic=True)} if "kl" in include_set else {}),
            }
            for doc in results
        ]

    def close(self):
        """\
        Closes the engine.
        """
        if self.mdb is not None:
            self.mdb.close()
        self.mdb = None
