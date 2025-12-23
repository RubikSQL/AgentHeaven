"""
Generate pytest parametrize decorators from JSON configurations.

This module provides helpers to create pytest.mark.parametrize decorators
dynamically from test configurations.
"""

from typing import Any, Callable, List, Optional, Tuple
import pytest


def generate_parametrize(
    config_loader: Any,
    config_type: str,
    test_name: Optional[str] = None,
    filter_func: Optional[Callable[[Any], bool]] = None,
) -> Tuple[str, List[Any], List[str]]:
    """
    Generate pytest parametrize arguments from config loader.

    Args:
        config_loader: ConfigLoader instance
        config_type: Type of configuration (cache, db, vdb, klstore, klengine)
        test_name: Test name for path resolution
        filter_func: Optional function to filter configurations

    Returns:
        Tuple of (param_name, param_values, param_ids)
    """
    if config_type == "cache":
        configs = config_loader.get_cache_configs(test_name)
        param_name = "cache_config"
    elif config_type == "db":
        configs = config_loader.get_db_configs(test_name)
        param_name = "db_config"
    elif config_type == "vdb":
        configs = config_loader.get_vdb_configs(test_name)
        param_name = "vdb_config"
    elif config_type == "klstore":
        configs = config_loader.get_klstore_configs(test_name)
        param_name = "klstore_config"
    elif config_type == "klengine":
        configs = config_loader.get_klengine_configs(test_name)
        param_name = "klengine_config"
    else:
        raise ValueError(f"Unknown config type: {config_type}")

    # Apply filter if provided
    if filter_func is not None:
        configs = [c for c in configs if filter_func(c)]

    # Generate IDs
    ids = [config_loader.get_config_id(config_type, config) for config in configs]

    return param_name, configs, ids


def minimal_cache_filter(config: Tuple[str, Any, Any]) -> bool:
    """Filter for minimal cache configurations."""
    cache_type, backend, path = config
    # Include: InMemCache, JsonCache, DatabaseCache with SQLite file, MongoCache
    if cache_type == "InMemCache":
        return True
    if cache_type == "JsonCache":
        return True
    if cache_type == "DatabaseCache" and backend == "sqlite" and path and path != ":memory:":
        return True
    if cache_type == "MongoCache":
        return True
    return False


def minimal_db_filter(config: Tuple[str, Optional[str]]) -> bool:
    """Filter for minimal database configurations."""
    backend, path = config
    # Include: SQLite memory and file
    if backend == "sqlite":
        return True
    return False


def minimal_vdb_filter(config: Tuple[str, Optional[str]]) -> bool:
    """Filter for minimal VDB configurations."""
    backend, path = config
    # Include: lancedb, chromalite, and pgvector
    if backend in ["lancedb", "chromalite", "pgvector"]:
        return True
    return False


def minimal_mdb_filter(config: Tuple[str, Optional[str]]) -> bool:
    """Filter for minimal MDB configurations."""
    # In tests.json, mdb config is just the db name and collection name
    db_name, collection_name = config
    # For minimal, we can just check if it's not empty
    return bool(db_name and collection_name)


def minimal_klstore_filter(config: Tuple[str, List[Any]]) -> bool:
    """Filter for minimal KLStore configurations."""
    store_type, backend_args = config
    # Include a representative from each store type
    if store_type == "CacheKLStore":
        # Only InMemCache
        cache_type = backend_args[0]
        return cache_type == "InMemCache"
    elif store_type == "DatabaseKLStore":
        # Only SQLite memory and file
        db_backend = backend_args[0]
        return db_backend == "sqlite"
    elif store_type == "VectorKLStore":
        # Only lancedb
        vdb_backend = backend_args[0]
        return vdb_backend == "lancedb"
    elif store_type == "MongoKLStore":
        # Include MongoDB
        return True
    return False


def minimal_klengine_filter(config: Tuple[str, List[Any], Any, bool]) -> bool:
    """Filter for minimal KLEngine configurations."""
    engine_type, store_args, engine_backend_args, inplace = config
    store_type, backend_args = store_args

    # For DAACKLEngine: Only InMemCache-based
    if engine_type == "DAACKLEngine":
        if store_type == "CacheKLStore":
            cache_type = backend_args[0]
            return cache_type == "InMemCache" and engine_backend_args is None
        return False

    # For FacetKLEngine: Only SQLite-based with inplace=True, and one with inplace=False
    elif engine_type == "FacetKLEngine":
        if store_type == "DatabaseKLStore":
            db_backend = backend_args[0]
            # Include SQLite with both inplace modes
            if db_backend == "sqlite" and engine_backend_args is None:
                return True
        return False

    # For VectorKLEngine: Only lancedb-based
    elif engine_type == "VectorKLEngine":
        if store_type == "VectorKLStore":
            vdb_backend = backend_args[0]
            return vdb_backend == "lancedb" and engine_backend_args is None
        return False

    # For MongoKLEngine: Only MongoKLStore-based with inplace=True
    elif engine_type == "MongoKLEngine":
        if store_type == "MongoKLStore":
            return engine_backend_args is None and inplace is True
        return False

    return False


def representative_cache_filter(config: Tuple[str, Any, Any]) -> bool:
    """Filter for representative cache configurations."""
    cache_type, backend, path = config
    # Include: InMemCache, JsonCache, DiskCache, DatabaseCache with SQLite and PostgreSQL, MongoCache
    if cache_type in ["InMemCache", "JsonCache", "DiskCache"]:
        return True
    if cache_type == "DatabaseCache" and backend in ["sqlite", "postgresql"]:
        return True
    if cache_type == "MongoCache":
        return True
    return False


def representative_db_filter(config: Tuple[str, Optional[str]]) -> bool:
    """Filter for representative database configurations."""
    backend, path = config
    # Include: SQLite (both memory and file) and PostgreSQL
    if backend in ["sqlite", "postgresql"]:
        return True
    return False


def representative_vdb_filter(config: Tuple[str, Optional[str]]) -> bool:
    """Filter for representative VDB configurations."""
    backend, path = config
    # Include: lancedb, chromalite, chroma
    if backend in ["lancedb", "chromalite", "chroma"]:
        return True
    return False


def representative_mdb_filter(config: Tuple[str, Optional[str]]) -> bool:
    """Filter for representative MDB configurations."""
    db_name, collection_name = config
    # All defined MDB configs are representative
    return bool(db_name and collection_name)


def representative_klstore_filter(config: Tuple[str, List[Any]]) -> bool:
    """Filter for representative KLStore configurations."""
    store_type, backend_args = config
    # Include multiple representatives from each store type
    if store_type == "CacheKLStore":
        cache_type = backend_args[0]
        return cache_type in ["InMemCache", "JsonCache"]
    elif store_type == "DatabaseKLStore":
        db_backend = backend_args[0]
        return db_backend in ["sqlite", "postgresql"]
    elif store_type == "VectorKLStore":
        vdb_backend = backend_args[0]
        return vdb_backend in ["lancedb", "chromalite"]
    return False


def representative_klengine_filter(config: Tuple[str, List[Any], Any, bool]) -> bool:
    """Filter for representative KLEngine configurations."""
    engine_type, store_args, engine_backend_args, inplace = config
    store_type, backend_args = store_args

    # For each engine type, include key representatives
    if engine_type == "DAACKLEngine":
        if store_type == "CacheKLStore":
            cache_type = backend_args[0]
            return cache_type == "InMemCache" and engine_backend_args is None
        elif store_type == "DatabaseKLStore":
            db_backend = backend_args[0]
            return db_backend == "sqlite" and engine_backend_args is None
        return False

    elif engine_type == "FacetKLEngine":
        if store_type == "DatabaseKLStore":
            db_backend = backend_args[0]
            # Include SQLite and PostgreSQL with both inplace modes
            if db_backend in ["sqlite", "postgresql"]:
                return True
        return False

    elif engine_type == "VectorKLEngine":
        if store_type == "VectorKLStore":
            vdb_backend = backend_args[0]
            return vdb_backend in ["lancedb", "chromalite"] and engine_backend_args is None
        return False

    elif engine_type == "MongoKLEngine":
        # Include MongoKLStore with inplace=True and CacheKLStore with inplace=False
        if store_type == "MongoKLStore":
            return engine_backend_args is None and inplace is True
        elif store_type == "CacheKLStore":
            cache_type = backend_args[0]
            return cache_type == "InMemCache" and engine_backend_args is not None
        return False

    return False
