from __future__ import annotations

__all__ = [
    "VectorDatabase",
]

from ahvn.llm.base import LLM
from .vdb_utils import *
from ..basic.request_utils import NetworkProxy

from ..basic.log_utils import get_logger
from ..deps import deps

logger = get_logger(__name__)

_llama_index_types = None


def get_llama_index_types():
    global _llama_index_types
    if _llama_index_types is None:
        _llama_index_types = deps.load("llama_index.core.vector_stores.types")
    return _llama_index_types


from typing import Any, Optional, Union, Callable, List, Tuple, Dict, Iterable, TYPE_CHECKING

if TYPE_CHECKING:
    from llama_index.core.schema import TextNode
    from llama_index.core.vector_stores.types import VectorStore, VectorStoreQuery

VDB_BACKEND_COLLECTION_MAPPING = {
    "simple": None,
    "lancedb": "table_name",
    "chroma": None,
    "milvus": "collection_name",
    "pgvector": "database",
}


class VectorDatabase(object):
    def __init__(
        self,
        collection: Optional[str] = None,
        provider: Optional[str] = None,
        encoder: Union[Callable[[Any], str], Tuple[Callable[[Any], str], Callable[[Any], str]]] = None,
        embedder: Optional[Union[Callable[[str], List[float]], Tuple[Callable[[str], List[float]], Callable[[str], List[float]]], "LLM"]] = None,
        connect: bool = False,
        **kwargs,
    ):
        super().__init__()
        self.config = resolve_vdb_config(collection=collection, provider=provider, **kwargs)
        self.backend = self.config.pop("backend", None)
        self.collection = self.config.pop("collection", None)
        collection_attr = VDB_BACKEND_COLLECTION_MAPPING.get(self.backend)
        if collection_attr:
            self.config = {collection_attr: self.collection} | self.config
        self.proxy = NetworkProxy(
            http_proxy=self.config.pop("http_proxy", None),
            https_proxy=self.config.pop("https_proxy", None),
        )
        (self.k_encoder, self.q_encoder), (self.k_embedder, self.q_embedder), self.k_dim, self.q_dim = parse_encoder_embedder(
            encoder=encoder,
            embedder=embedder,
        )
        self.vdb = None
        if connect:
            self.connect()

    def connect(self) -> VectorStore:
        """Create the appropriate vector store based on provider.

        Returns:
            LlamaIndex VectorStore instance.
        """
        self.vdb = None
        if self.backend == "simple":
            # TODO: SimpleVectorStore in llama_index doesn't persist TextNode objects by default
            # (it stores embeddings and ids), which makes operations like getting all
            # nodes or deleting by node_id unreliable for our use-case.
            from llama_index.core.vector_stores import SimpleVectorStore

            self.vdb = SimpleVectorStore(**self.config)
            return
        if self.backend == "lancedb":
            from llama_index.vector_stores.lancedb import LanceDBVectorStore

            self.vdb = LanceDBVectorStore(**self.config)
            return
        if self.backend == "chroma":
            import chromadb
            from llama_index.vector_stores.chroma import ChromaVectorStore

            mode = self.config.pop("mode", "ephemeral")
            client = {
                "ephemeral": chromadb.EphemeralClient,
                "persistent": chromadb.PersistentClient,
                "http": chromadb.HttpClient,
                "cloud": chromadb.CloudClient,
            }[mode](**self.config)
            collection = client.get_or_create_collection(self.collection)
            self.vdb = ChromaVectorStore(chroma_collection=collection)
            return
        if self.backend == "milvus":
            from pymilvus import utility
            from llama_index.vector_stores.milvus import MilvusVectorStore

            config = {"dim": self.k_dim} | self.config
            self.vdb = MilvusVectorStore(**config)
            self.vdb.client.load_collection(self.vdb.collection_name)
            utility.wait_for_loading_complete(self.vdb.collection_name, using=config.get("alias", "default"))
            return
        if self.backend == "pgvector":
            from llama_index.vector_stores.postgres import PGVectorStore
            from ..db.db_utils import resolve_db_config, create_database_engine

            # Convert config parameters to PGVectorStore format
            pg_config = {"embed_dim": self.k_dim}

            db_kwargs = self.config | {"dialect": "postgresql", "driver": "psycopg2"}
            db_config, conn_args = resolve_db_config(**db_kwargs)
            connection_string = db_config.get("url")
            pg_config["connection_string"] = connection_string
            pg_config |= {k: v for k, v in db_config.items() if k != "url"}

            # Create both sync and async engines to satisfy PGVectorStore requirements
            sync_engine = create_database_engine(config=db_config, conn_args=conn_args)
            pg_config["engine"] = sync_engine
            try:
                from sqlalchemy.ext.asyncio import create_async_engine

                async_connection_string = connection_string.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
                async_engine = create_async_engine(async_connection_string)
                pg_config["async_engine"] = async_engine
            except ImportError:
                logger.warning("asyncpg not installed, skipping async_engine creation for PGVectorStore.")
                pg_config["async_engine"] = None
            self.vdb = PGVectorStore(**pg_config)
            return

    def close(self):
        if hasattr(self, "vdb") and (self.vdb is not None) and hasattr(self.vdb, "close"):
            self.vdb.close()
        self.vdb = None

    def k_encode(self, kl: Any) -> str:
        return self.k_encoder(kl)

    def k_embed(self, encoded_kl: str) -> List[float]:
        return self.k_embedder(encoded_kl)

    def batch_k_encode(self, kls: Iterable[Any]) -> List[str]:
        if not len(kls):
            return list()
        return [self.k_encode(kl) for kl in kls]

    def batch_k_embed(self, encoded_kls: List[str]) -> List[List[float]]:
        if not len(encoded_kls):
            return list()
        return self.k_embedder(encoded_kls)

    def q_encode(self, query: Any) -> str:
        return self.q_encoder(query)

    def q_embed(self, encoded_query: str) -> List[float]:
        return self.q_embedder(encoded_query)

    def batch_q_encode(self, queries: Iterable[str]) -> List[str]:
        if not len(queries):
            return list()
        return [self.q_encode(query) for query in queries]

    def batch_q_embed(self, encoded_queries: List[str]) -> List[List[float]]:
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
        encoded_text = self.k_encode(obj)
        embedding = self.k_embed(encoded_text)
        return encoded_text, embedding

    def batch_k_encode_embed(self, objs: Iterable[Any]) -> List[Tuple[str, List[float]]]:
        """Encode a batch of objects and generate their embeddings.

        Args:
            objs: Iterable of objects to encode and embed.

        Returns:
            List of tuples of (encoded_text, embedding).
        """
        if not len(objs):
            return list()
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
        """Encode a batch of queries and generate their embeddings.

        Args:
            queries: Iterable of queries to encode and embed.

        Returns:
            List of tuples of (encoded_text, embedding).
        """
        if not len(queries):
            return list()
        q_encoded_texts = self.batch_q_encode(queries)
        q_embeddings = self.batch_q_embed(q_encoded_texts)
        return list(zip(q_encoded_texts, q_embeddings))

    def search(self, query=None, embedding=None, topk=5, filters=None, *args, **kwargs):
        if (query is None) and (embedding is None):
            raise ValueError("Either 'query' or 'embedding' must be provided for search.")
        return get_llama_index_types().VectorStoreQuery(
            query_embedding=embedding if embedding is not None else self.q_embed(self.q_encode(query)),
            similarity_top_k=topk,
            filters=filters,
            *args,
            **kwargs,
        )

    def _record_to_node(self, record: Dict[str, Any]) -> "TextNode":
        """Convert a record dictionary to a TextNode.

        Args:
            record: Dictionary containing the record data with vector and text fields.

        Returns:
            TextNode instance.
        """
        from llama_index.core.schema import TextNode

        # Extract vector and text from record (try common field names)
        vector = record.get("vector") or record.get("_vector")
        text = record.get("text") or record.get("_text", "")

        # Create metadata (only include basic scalar fields)
        metadata = {}
        for key, value in record.items():
            if key not in ["vector", "text", "_vector", "_text"]:
                # Only include basic scalar types and convert ID to string
                if isinstance(value, (str, int, float, bool)) or value is None:
                    if key == "id":
                        metadata[key] = str(value)
                    else:
                        metadata[key] = value
                # Skip all complex objects (lists, dicts, sets, datetime, etc.)
                else:
                    continue

        # Create TextNode
        return TextNode(text=text, embedding=vector, metadata=metadata, id_=str(metadata.get("id", "")))

    def insert(self, record: Dict[str, Any]) -> None:
        """Insert a single record into the vector database.

        Args:
            record: Dictionary containing the record data with vector and text fields.
        """
        node = self._record_to_node(record)
        self.vdb.add([node])

    def delete(self, record_id: Union[str, int]) -> None:
        """Delete a record from the vector database by ID.

        Args:
            record_id: ID of the record to delete.
        """
        self.vdb.delete_nodes([str(record_id)])

    def batch_insert(self, records: List[Dict[str, Any]]) -> None:
        """Insert multiple records into the vector database.

        Args:
            records: List of dictionaries containing record data.
        """
        nodes = [self._record_to_node(record) for record in records]
        self.vdb.add(nodes)

    def _get_all_nodes(self) -> List["TextNode"]:
        """Get all nodes from the vector database in a backend-agnostic way.

        Some backends (like Milvus, PGVector) don't support node_ids=None to get all nodes.
        This method tries multiple strategies to retrieve all nodes.

        Returns:
            List of all TextNode objects in the database.
        """
        try:
            return self.vdb.get_nodes(node_ids=None)
        except (ValueError, TypeError, AssertionError, NotImplementedError):
            try:
                # Query with a dummy vector and high limit to get all nodes
                # Milvus has a max limit of 16384
                query_result = self.vdb.query(
                    get_llama_index_types().VectorStoreQuery(
                        query_embedding=[0.0] * self.k_dim,
                        similarity_top_k=16384,  # Milvus max limit
                    )
                )
                logger.warning(
                    "Tried get_nodes with node_ids=None, falling back to high-limit query (16384). This may not retrieve all nodes if more than 16384 exist."
                )
                if query_result.ids:
                    return self.vdb.get_nodes(node_ids=query_result.ids)
                return []
            except Exception:
                return []

    def clear(self) -> None:
        """Clear all records from the vector database."""
        # Get all nodes and delete by IDs (works for all backends)
        all_nodes = self._get_all_nodes()
        if all_nodes:
            node_ids = [node.node_id for node in all_nodes]
            self.vdb.delete_nodes(node_ids)

    def flush(self) -> None:
        """Flush any pending operations to the vector database."""
        # Milvus
        if hasattr(self.vdb, "client") and hasattr(self.vdb.client, "flush"):
            from pymilvus import utility

            self.vdb.client.load_collection(self.vdb.collection_name)
            utility.wait_for_loading_complete(self.vdb.collection_name)
            self.vdb.client.flush(self.vdb.collection_name)
            return
