"""Universal vector KL engine implementation."""

from __future__ import annotations

__all__ = [
    "VectorKLEngine",
]
from typing import Any, Dict, Iterable, List, Optional, Generator, Tuple, TYPE_CHECKING

from ..utils.deps import deps

if TYPE_CHECKING:
    from llama_index.core.vector_stores.types import VectorStoreQuery
    from llama_index.core.schema import TextNode

from ..utils.vdb.compiler import VectorCompiler
from ..utils.klop import KLOp
from ..utils.basic.config_utils import HEAVEN_CM
from ..utils.basic.log_utils import get_logger
from ..utils.basic.debug_utils import raise_mismatch
from ..utils.basic.progress_utils import Progress

from .base import BaseKLEngine
from ..ukf.base import BaseUKF
from ..ukf.templates.basic.dummy import DummyUKFT
from ..adapter.vdb import VdbUKFAdapter
from ..klstore.vdb_store import VectorKLStore
from ..utils.vdb.base import VectorDatabase

logger = get_logger(__name__)


def get_llama_index_types():
    return deps.load("llama_index.core.vector_stores.types")


class VectorKLEngine(BaseKLEngine):
    """\
    A vector-based search KLEngine implementation that provides multiple search interfaces.

    This class extends BaseKLEngine with specialized search methods:
    - Vector similarity search through the default _search method
    - Filtered vector search through _search method
    - LLM-powered natural language to vector search through _search_auto method

    The engine is designed to work with vector data that can be searched using
    semantic similarity and filtered using various metadata conditions.

    Search Methods:
        _search_vector(query, topk, include, **filters): Perform vector similarity search with optional metadata filters.
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
        storage: VectorKLStore,
        inplace: bool = True,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        filters: Dict[str, Any] = None,
        name: Optional[str] = None,
        condition: Optional[Any] = None,
        *args,
        **kwargs,
    ):
        """Initialize the VectorKLEngine.

        Args:
            storage: attach VectorKLEngine to a VectorKLStore (required).
            inplace: If True, search directly on storage vector database; if False, create a copied collection with included fields.
            include (if inplace=False): List of BaseUKF field names to include. If None, includes all fields. Default is None.
            exclude (if inplace=False): List of BaseUKF field names to exclude. If None, excludes no fields. Default is None.
                Notice that exclude is applied after include, so if a field is in both include and exclude,
                it will be excluded. It is recommended to use only one of include or exclude.
            filters: global filters that will be applied to all searches.
            name: Name of the KLEngine instance. If None, defaults to "{storage.name}_vec_idx".
            condition: Optional upsert/insert condition to apply to the KLEngine.
                KLs that do not satisfy the condition will be ignored. If None, all KLs are accepted.
            *args: Additional positional arguments passed to VectorKLEngine.
            **kwargs: Additional keyword arguments passed to VectorKLEngine.
        """
        if inplace and not isinstance(storage, VectorKLStore):
            raise ValueError("When inplace=True, storage must be a VectorKLStore instance")

        super().__init__(storage=storage, inplace=inplace, name=name or f"{storage.name}_vec_idx", condition=condition, *args, **kwargs)
        self.exprs = None if not filters else KLOp.expr(**filters)

        if self.inplace:
            self.vdb = self.storage.vdb
            self.adapter = self.storage.adapter
        else:
            provider = kwargs.get("provider") or HEAVEN_CM.get("vdb.default_provider")
            collection = kwargs.get("collection") or self.name or HEAVEN_CM.get(f"vdb.providers.{provider}.collection")
            encoder = kwargs.get("encoder")
            embedder = kwargs.get("embedder")
            connection_args = {k: v for k, v in kwargs.items() if k not in ["collection", "provider", "encoder", "embedder", "include", "exclude"]}
            self.vdb = VectorDatabase(collection=collection, provider=provider, encoder=encoder, embedder=embedder, **connection_args)
            self.vdb.connect()  # Connect to the vector database
            self.adapter = VdbUKFAdapter(backend=self.vdb.backend, name=self.name, include=include, exclude=exclude)
        self._init()

        self.recoverable = self.adapter.recoverable

    def _init(self):
        if self.inplace:
            return
        # Initialize the collection with a dummy node, then clear it
        # This ensures the collection schema is properly set up
        dummy = DummyUKFT(name="<dummy>", content="This is a dummy node to initialize the collection.")
        self.vdb.vdb.add(self._batch_convert([dummy]))
        self.vdb.flush()
        # Remove the dummy node
        self.remove(dummy.id)
        self.vdb.flush()

    def _batch_convert(self, kls: Iterable[BaseUKF]) -> List[TextNode]:
        kls_list = list(kls)
        non_dummy_kls = [kl for kl in kls_list if not isinstance(kl, DummyUKFT)]
        non_dymmy_key_embeddings = self.vdb.batch_k_encode_embed(non_dummy_kls) if non_dummy_kls else []
        non_dummy_mapping = dict(zip([kl.id for kl in non_dummy_kls], non_dymmy_key_embeddings))
        dummy_emb = self.vdb.k_embed("<dummy>")
        nodes = []
        for kl in kls_list:
            if isinstance(kl, DummyUKFT):
                key, embedding = "<dummy>", dummy_emb
            else:
                key, embedding = non_dummy_mapping[kl.id]
            nodes.append(self.adapter.from_ukf(kl=kl, key=key, embedding=embedding))
        return nodes

    def _search_vector(
        self, query: str = None, topk: int = 20, fetchk: Optional[int] = 100, include: Optional[Iterable[str]] = None, *args, **kwargs
    ) -> List[Dict[str, Any]]:
        """\
        Perform a vector similarity search using metadata filters.

        This method applies structured filters to search through the knowledge items
        using vector similarity combined with metadata filtering.

        Args:
            query (str): The text query to search for using vector similarity.
                If None, only filter-based search is performed without vector search.
            topk (int): Number of top results to return. Default is 20.
            fetchk (Optional[int]): Number of top results to fetch from the vector database before applying filters or reranking.
            include (Optional[Iterable[str]]): The keys to include in the search results.
                Supported keys include:
                - 'id': The unique identifier of the KL (BaseUKF.id).
                - 'kl': The KL object itself (BaseUKF).
                - 'score': The similarity score from vector search.
                - 'filter': The applied metadata filter for debugging.
                - 'vsq': The VectorStoreQuery object for debugging.
                - 'key': The vector search key (_key field).
                - 'embedding': The vector embedding (_vec field).
                Defaults to None, which resolves to ['id', 'kl', 'score'].
            *args: Additional positional arguments.
            **kwargs: Filter conditions as keyword arguments.

        Returns:
            List[Dict[str, Any]]: The search results matching the applied filters and query.

        Raises:
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

        _supported_includes = ["id", "kl", "score", "filter", "vsq", "key", "embedding", "qkey", "qembedding"]
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
        metadata_filters = VectorCompiler.compile(expr=self.exprs, **kwargs)
        if query is None:
            query_key, query_embedding = None, None
        else:
            query_key, query_embedding = self.vdb.q_encode_embed(query)
        fetchk = max(fetchk or topk, topk, 0)  # TODO: throw in fetchk somewhere in VDB query
        query_stmt: VectorStoreQuery = get_llama_index_types().VectorStoreQuery(
            query_embedding=query_embedding,
            similarity_top_k=topk,
            filters=metadata_filters,
        )
        try:
            results = self.vdb.vdb.query(query_stmt)
        except Exception as e:
            logger.error(f"Vector database query failed: {e}")
            return list()

        nodes = results.nodes or []
        similarities = results.similarities or [None] * len(nodes)
        return [
            {
                "id": int(node.node_id) if isinstance(node.node_id, (int, str)) and str(node.node_id).isdigit() else node.node_id,
                **({"score": float(similarity) if similarity is not None else 0.0} if "score" in include_set else {}),
                **({"filter": metadata_filters} if "filter" in include_set else {}),
                **({"vsq": query_stmt} if "vsq" in include_set else {}),
                **({"key": query_key} if "key" in include_set else {}),
                **({"embedding": query_embedding} if "embedding" in include_set else {}),
                **({"qkey": query_key} if "qkey" in include_set else {}),
                **({"qembedding": query_embedding} if "qembedding" in include_set else {}),
                **({"kl": self.adapter.to_ukf(entity=node)} if self.recoverable and ("kl" in include_set) else {}),
            }
            for node, similarity in zip(nodes, similarities)
        ]

    def _search(
        self, query: str = None, topk: int = 20, fetchk: Optional[int] = 100, include: Optional[Iterable[str]] = None, *args, **kwargs
    ) -> List[Dict[str, Any]]:
        """Alias for _search_vector for default search behavior."""
        return self._search_vector(query=query, topk=topk, fetchk=fetchk, include=include, *args, **kwargs)

    def _get(self, key: int, default: Any = ...) -> Optional[BaseUKF]:
        if not self.recoverable:
            return default
        return VectorKLStore._get(self, key, default=default)

    def _has(self, key: int) -> bool:
        return VectorKLStore._has(self, key)

    def _upsert(self, kl: BaseUKF, **kwargs):
        if self.inplace:
            return
        VectorKLStore._upsert(self, kl, **kwargs)

    def _insert(self, kl, **kwargs):
        if self.inplace:
            return
        VectorKLStore._insert(self, kl, **kwargs)

    def _batch_upsert(self, kls, progress: Progress = None, **kwargs):
        if self.inplace:
            return
        VectorKLStore._batch_upsert(self, kls, progress=progress, **kwargs)

    def _batch_insert(self, kls, progress: Progress = None, **kwargs):
        if self.inplace:
            return
        VectorKLStore._batch_insert(self, kls, progress=progress, **kwargs)

    def _remove(self, key: int, **kwargs):
        if self.inplace:
            return
        VectorKLStore._remove(self, key, **kwargs)

    def _batch_remove(self, keys, progress: Progress = None, **kwargs):
        if self.inplace:
            return
        VectorKLStore._batch_remove(self, keys, progress=progress, **kwargs)

    def __len__(self) -> int:
        if self.inplace:
            return len(self.storage)
        else:
            return len(self.vdb._get_all_nodes())

    def _itervalues(self) -> Generator[BaseUKF, None, None]:
        if self.inplace:
            yield from self.storage._itervalues()
        else:
            for node in self.vdb._get_all_nodes():
                yield self.adapter.to_ukf(entity=node)

    def _clear(self):
        if self.inplace:
            return
        self.vdb.clear()

    def close(self):
        """\
        Closes the engine.
        """
        if self.vdb is not None:
            self.vdb.close()
        self.vdb = None

    def k_encode(self, kl: BaseUKF) -> str:
        """Encode a BaseUKF using the VDB's key encoder."""
        return self.vdb.k_encode(kl)

    def k_embed(self, encoded_kl: str) -> List[float]:
        """Embed an encoded BaseUKF using the VDB's key embedder."""
        return self.vdb.k_embed(encoded_kl)

    def batch_k_encode(self, kls: Iterable[BaseUKF]) -> List[str]:
        """Encode a batch of BaseUKFs using the VDB's key encoder."""
        return self.vdb.batch_k_encode(kls)

    def batch_k_embed(self, encoded_kls: List[str]) -> List[List[float]]:
        """Embed a batch of encoded BaseUKFs using the VDB's key embedder."""
        return self.vdb.batch_k_embed(encoded_kls)

    def q_encode(self, query: str) -> str:
        """Encode a query string using the VDB's query encoder."""
        return self.vdb.q_encode(query)

    def q_embed(self, encoded_query: str) -> List[float]:
        """Embed an encoded query string using the VDB's query embedder."""
        return self.vdb.q_embed(encoded_query)

    def batch_q_encode(self, queries: Iterable[str]) -> List[str]:
        """Encode a batch of query strings using the VDB's query encoder."""
        return self.vdb.batch_q_encode(queries)

    def batch_q_embed(self, encoded_queries: List[str]) -> List[List[float]]:
        """Embed a batch of encoded query strings using the VDB's query embedder."""
        return self.vdb.batch_q_embed(encoded_queries)

    def k_encode_embed(self, kl: BaseUKF) -> Tuple[str, List[float]]:
        """Encode and embed a BaseUKF using the VDB's key encoder and embedder."""
        return self.vdb.k_encode_embed(kl)

    def batch_k_encode_embed(self, kls: Iterable[BaseUKF]) -> List[Tuple[str, List[float]]]:
        """Encode and embed a batch of BaseUKFs using the VDB's key encoder and embedder."""
        return self.vdb.batch_k_encode_embed(kls)

    def q_encode_embed(self, query: str) -> Tuple[str, List[float]]:
        """Encode and embed a query string using the VDB's query encoder and embedder."""
        return self.vdb.q_encode_embed(query)

    def batch_q_encode_embed(self, queries: Iterable[str]) -> List[Tuple[str, List[float]]]:
        """Encode and embed a batch of query strings using the VDB's query encoder and embedder."""
        return self.vdb.batch_q_encode_embed(queries)

    @property
    def embedding_field(self):
        """Get the vector field name used by this engine."""
        return getattr(self.adapter, "embedding_field", "_vec")

    @property
    def adapter(self):
        """Get the adapter used by this engine."""
        return self._adapter if hasattr(self, "_adapter") else None

    @adapter.setter
    def adapter(self, value):
        """Set the adapter used by this engine."""
        self._adapter = value
