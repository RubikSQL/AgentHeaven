"""
Universal factory for creating test instances from JSON configurations.

This module provides factory functions that can instantiate any test component
(cache, database, vdb, klstore, klengine) from JSON configuration data.
"""

import sys
import uuid
from pathlib import Path
from typing import Any, Optional, Tuple

# Add src to Python path for imports
ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _get_short_name(label: str, length: int = 8) -> str:
    """Generate a short hash from label for naming test components.

    Ensures the name starts with 't' to comply with naming requirements
    (e.g., Milvus collection names must start with underscore or letter).

    Args:
        label: The label to hash
        length: Length of the hash (default: 8)

    Returns:
        Short name string starting with 't'
    """
    from ahvn.utils import fmt_short_hash, md5hash

    hash_str = fmt_short_hash(md5hash(label), length=length)
    return f"t{hash_str}"


class UniversalFactory:
    """Universal factory for creating test instances from JSON configurations."""

    @staticmethod
    def create_cache(cache_type: str, backend: Optional[str], path: Optional[str], label: Optional[str] = None) -> Any:
        """
        Create a cache instance from JSON configuration.

        Args:
            cache_type: Cache type (InMemCache, DiskCache, JsonCache, DatabaseCache, MongoCache)
            backend: Backend type for DatabaseCache (sqlite, duckdb, postgresql, mysql, mssql, etc.)
            path: Path for file-based caches, database path, or MongoDB collection name
            label: Label for generating short names (optional)

        Returns:
            Cache instance
        """
        from ahvn.cache import InMemCache, DiskCache, JsonCache, DatabaseCache, MongoCache

        if cache_type == "InMemCache":
            return InMemCache()

        elif cache_type == "DiskCache":
            if path is None:
                raise ValueError("DiskCache requires a path")
            return DiskCache(path=path)

        elif cache_type == "JsonCache":
            if path is None:
                raise ValueError("JsonCache requires a path")
            return JsonCache(path=path)

        elif cache_type == "DatabaseCache":
            if backend is None:
                raise ValueError("DatabaseCache requires a backend")

            # Handle database path resolution
            if path is None:
                # Generate a unique database name for external databases
                if backend in ["postgresql", "pg"]:
                    if label:
                        db_name = f"pytest_{_get_short_name(label)}"
                    else:
                        db_name = f"pytest_{_get_short_name(str(uuid.uuid4()))}"
                    return DatabaseCache(provider=backend, database=db_name)
                elif backend in ["mysql"]:
                    if label:
                        db_name = f"pytest_{_get_short_name(label)}"
                    else:
                        db_name = f"pytest_{_get_short_name(str(uuid.uuid4()))}"
                    return DatabaseCache(provider=backend, database=db_name)
                else:
                    raise ValueError(f"DatabaseCache with backend {backend} requires a path")

            return DatabaseCache(provider=backend, database=path)

        elif cache_type == "MongoCache":
            # For MongoCache, path is the collection name
            # Database name is resolved from config or defaults
            if path is None:
                raise ValueError("MongoCache requires a collection name")
            return MongoCache(collection=path)

        else:
            raise ValueError(f"Unknown cache type: {cache_type}")

    @staticmethod
    def create_database(backend: str, path: Optional[str], label: Optional[str] = None) -> Any:
        """
        Create a database instance from JSON configuration.

        Args:
            backend: Database backend (sqlite, duckdb, postgresql, mysql, mssql, etc.)
            path: Database path or name
            label: Label for generating short names (optional)

        Returns:
            Database instance
        """
        from ahvn.utils.db import Database

        # Map backend names
        provider_map = {
            "sqlite": "sqlite",
            "duckdb": "duckdb",
            "postgresql": "pg",
            "mysql": "mysql",
            "pg": "pg",
        }

        provider = provider_map.get(backend, backend)

        # Handle database path/name resolution
        if path is None:
            # Generate unique database name for external databases
            if provider in ["pg", "mysql"]:
                if label:
                    db_name = f"pytest_{_get_short_name(label)}"
                else:
                    db_name = f"pytest_{_get_short_name(str(uuid.uuid4()))}"
                return Database(provider=provider, database=db_name)
            else:
                raise ValueError(f"Database backend {backend} requires a path")

        return Database(provider=provider, database=path)

    @staticmethod
    def create_vdb(backend: str, path: Optional[str], label: Optional[str] = None) -> Any:
        """
        Create a vector database instance from JSON configuration.

        Args:
            backend: VDB backend (lancedb, chromalite, chroma, milvuslite)
            path: Database path (None for in-memory)
            label: Label for generating short names (optional)

        Returns:
            VectorDatabase instance
        """
        from ahvn.utils.vdb.base import VectorDatabase
        from .mock_embedder import create_mock_encoder_embedder

        # Create mock encoder and embedder for testing
        # Use 128 dimensions consistently across all tests
        encoder, embedder = create_mock_encoder_embedder(dim=128)

        # Generate short name if label provided
        name = _get_short_name(label) if label else None
        collection_name = f"{name}_collection" if name else "test_collection"

        if backend == "lancedb":
            if path is None:
                raise ValueError("LanceDB requires a path")
            return VectorDatabase(
                provider="lancedb",
                database=path,
                collection=collection_name,
                encoder=encoder,
                embedder=embedder,
                connect=True,
            )

        elif backend == "chromalite":
            # ChromaLite uses in-memory by default
            return VectorDatabase(
                provider="chromalite",
                collection=collection_name,
                encoder=encoder,
                embedder=embedder,
                connect=True,
            )

        elif backend == "chroma":
            if path is None:
                raise ValueError("Chroma requires a path")
            return VectorDatabase(
                provider="chroma",
                database=path,
                collection=collection_name,
                encoder=encoder,
                embedder=embedder,
                connect=True,
            )

        elif backend == "milvuslite":
            if path is None:
                raise ValueError("MilvusLite requires a path")
            # Generate unique connection alias for Milvus
            connection_alias = f"{name}_{uuid.uuid4().hex[:8]}" if name else f"conn_{uuid.uuid4().hex[:8]}"
            return VectorDatabase(
                provider="milvuslite",
                database=path,
                collection=collection_name,
                encoder=encoder,
                embedder=embedder,
                connection_alias=connection_alias,
                connect=True,
            )

        elif backend == "pgvector":
            # PGVector uses PostgreSQL with vector extension
            # Use default database name if none provided
            database = path if path else "vector_test"
            return VectorDatabase(
                provider="pgvector",
                database=database,
                collection=collection_name,
                encoder=encoder,
                embedder=embedder,
                connect=True,
            )

        else:
            raise ValueError(f"Unknown VDB backend: {backend}")

    @staticmethod
    def create_klstore(store_type: str, backend_args: list, label: Optional[str] = None) -> Any:
        """
        Create a KLStore instance from JSON configuration.

        Args:
            store_type: KLStore type (CacheKLStore, DatabaseKLStore, VectorKLStore, MongoKLStore)
            backend_args: Backend configuration arguments
            label: Label for generating short names (optional)

        Returns:
            KLStore instance
        """
        from ahvn.klstore import CacheKLStore, DatabaseKLStore, VectorKLStore, MongoKLStore

        if store_type == "CacheKLStore":
            # backend_args: [cache_type, backend, path]
            cache_type, backend, path = backend_args
            cache = UniversalFactory.create_cache(cache_type, backend, path, label=label)
            return CacheKLStore(cache=cache)

        elif store_type == "DatabaseKLStore":
            # backend_args: [db_backend, path]
            db_backend, path = backend_args
            # Generate short name if label provided
            name = _get_short_name(label) if label else None
            # DatabaseKLStore creates its own Database instance
            return DatabaseKLStore(database=path, provider=db_backend, name=name)

        elif store_type == "VectorKLStore":
            # backend_args: [vdb_backend, path]
            vdb_backend, path = backend_args
            # VectorKLStore creates its own VectorDatabase instance
            # Import mock embedder for vector store
            from .mock_embedder import create_mock_encoder_embedder

            encoder, embedder = create_mock_encoder_embedder(dim=128)

            # Generate short name if label provided
            name = _get_short_name(label) if label else None
            collection_name = f"{name}_collection" if name else "test_collection"

            # Build kwargs for VectorKLStore
            kwargs = {
                "collection": collection_name,
                "provider": vdb_backend,
                "database": path,
                "encoder": encoder,
                "embedder": embedder,
            }

            if name:
                kwargs["name"] = name

            return VectorKLStore(**kwargs)

        elif store_type == "MongoKLStore":
            # backend_args: database name (string)
            database = backend_args
            # Generate short name if label provided
            name = _get_short_name(label) if label else None
            collection_name = f"{name}_collection" if name else "test_collection"

            # Build kwargs for MongoKLStore
            kwargs = {
                "collection": collection_name,
                "database": database,
            }

            if name:
                kwargs["name"] = name

            return MongoKLStore(**kwargs)

        else:
            raise ValueError(f"Unknown KLStore type: {store_type}")

    @staticmethod
    def create_klengine(
        engine_type: str,
        store_args: list,
        engine_backend_args: Optional[Any],
        inplace: bool,
        label: Optional[str] = None,
    ) -> Any:
        """
        Create a KLEngine instance from JSON configuration.

        Args:
            engine_type: KLEngine type (DAACKLEngine, FacetKLEngine, VectorKLEngine, MongoKLEngine)
            store_args: Storage configuration arguments
            engine_backend_args: Additional engine backend arguments
            inplace: Whether to use inplace mode (for FacetKLEngine)
            label: Label for generating short names (optional)

        Returns:
            KLEngine instance
        """
        from ahvn.klengine import DAACKLEngine, FacetKLEngine, VectorKLEngine, MongoKLEngine, ScanKLEngine

        # Create storage from store_args with label for storage
        store_type, backend_args = store_args
        storage_label = f"{label}_storage" if label else None
        storage = UniversalFactory.create_klstore(store_type, backend_args, label=storage_label)

        if engine_type == "ScanKLEngine":
            # ScanKLEngine just needs storage (always inplace)
            return ScanKLEngine(storage=storage)

        elif engine_type == "DAACKLEngine":
            # DAACKLEngine just needs storage
            return DAACKLEngine(storage=storage)

        elif engine_type == "FacetKLEngine":
            # FacetKLEngine needs storage, optional index backend, and inplace flag
            if engine_backend_args is None:
                # No separate index backend, use storage directly
                return FacetKLEngine(storage=storage, inplace=inplace)
            else:
                # Create separate index database with label for index
                index_backend, index_path = engine_backend_args
                index_label = f"{label}_index" if label else None
                index_db = UniversalFactory.create_database(index_backend, index_path, label=index_label)
                return FacetKLEngine(storage=storage, index=index_db, inplace=inplace)

        elif engine_type == "VectorKLEngine":
            # VectorKLEngine needs storage and optional index backend
            if engine_backend_args is None:
                # No separate index backend, use storage directly
                return VectorKLEngine(storage=storage, inplace=True)
            else:
                # Create separate index vector database with label for index
                index_backend, index_path = engine_backend_args
                index_label = f"{label}_index" if label else None

                # Import mock embedder for index
                from .mock_embedder import create_mock_encoder_embedder

                encoder, embedder = create_mock_encoder_embedder(dim=128)

                # Generate short name for index if label provided
                name = _get_short_name(index_label) if index_label else None
                collection_name = f"{name}_engine" if name else "index_collection"

                # Build kwargs for VectorKLEngine
                engine_kwargs = {
                    "storage": storage,
                    "inplace": False,
                    "encoder": (encoder, encoder),  # Use same encoder for query
                    "embedder": embedder,
                    "provider": index_backend,
                    "database": index_path,
                    "collection": collection_name,
                }

                if name:
                    engine_kwargs["name"] = name

                # Add connection_alias for milvuslite
                if index_backend == "milvuslite":
                    engine_kwargs["connection_alias"] = f"{name}_{uuid.uuid4().hex[:8]}" if name else f"conn_{uuid.uuid4().hex[:8]}"

                return VectorKLEngine(**engine_kwargs)

        elif engine_type == "MongoKLEngine":
            # MongoKLEngine needs storage and optional database name
            if engine_backend_args is None:
                # No separate database, use storage directly (inplace=True)
                # Storage must be MongoKLStore
                return MongoKLEngine(storage=storage, inplace=True, sync=True)
            else:
                # Create separate MongoDB database with label for database (inplace=False)
                database_name = engine_backend_args
                # Resolve the database name with label
                if label:
                    resolved_database = database_name.replace("{name}", _get_short_name(label))
                else:
                    resolved_database = database_name.replace("{name}", _get_short_name(str(uuid.uuid4())))

                # Generate collection name
                name = _get_short_name(label) if label else None
                collection_name = f"{name}_engine" if name else "mongo_index_collection"

                return MongoKLEngine(storage=storage, inplace=False, database=resolved_database, collection=collection_name, sync=False)

        else:
            raise ValueError(f"Unknown KLEngine type: {engine_type}")

    @staticmethod
    def is_external_service(backend: str) -> bool:
        """
        Check if a backend requires external service.

        Args:
            backend: Backend name

        Returns:
            True if backend requires external service (PostgreSQL, MySQL)
        """
        return backend in ["postgresql", "pg", "mysql"]

    @staticmethod
    def check_service_available(backend: str) -> bool:
        """
        Check if an external service is available.

        Args:
            backend: Backend name (postgresql, mysql)

        Returns:
            True if service is available
        """
        if not UniversalFactory.is_external_service(backend):
            return True

        try:
            from ahvn.utils.db import Database

            # Map backend names
            provider_map = {
                "postgresql": "pg",
                "mysql": "mysql",
                "pg": "pg",
            }
            provider = provider_map.get(backend, backend)

            # Try to create a test connection
            test_db = Database(provider=provider, database="test_connection")
            test_db.execute("SELECT 1")
            test_db.close()
            return True
        except Exception:
            return False
