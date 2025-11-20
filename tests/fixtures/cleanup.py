"""
Unified cleanup handlers for test instances.

This module provides cleanup functions for all test component types,
ensuring proper resource disposal and avoiding leftover test data.
"""

import os
import shutil
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def cleanup_instance(instance: Any, instance_type: str) -> None:
    """
    Clean up a test instance based on its type.

    Args:
        instance: Instance to clean up
        instance_type: Type of instance (cache, database, vdb, klstore, klengine)
    """
    if instance_type == "cache":
        cleanup_cache(instance)
    elif instance_type == "database":
        cleanup_database(instance)
    elif instance_type == "vdb":
        cleanup_vdb(instance)
    elif instance_type == "klstore":
        cleanup_klstore(instance)
    elif instance_type == "klengine":
        cleanup_klengine(instance)
    else:
        logger.warning(f"Unknown instance type for cleanup: {instance_type}")


def cleanup_cache(cache: Any) -> None:
    """
    Clean up a cache instance.

    Args:
        cache: Cache instance to clean up
    """
    try:
        # Try to clear the cache
        if hasattr(cache, "clear"):
            cache.clear()

        # For DatabaseCache, drop the database
        if hasattr(cache, "__class__") and cache.__class__.__name__ == "DatabaseCache":
            if hasattr(cache, "_db"):
                cleanup_database(cache._db)

        # For MongoCache, drop the collection
        if hasattr(cache, "__class__") and cache.__class__.__name__ == "MongoCache":
            if hasattr(cache, "_mdb") and cache._mdb is not None:
                try:
                    cache._mdb.conn.drop()
                    cache._mdb.close()
                except Exception as e:
                    logger.warning(f"MongoCache cleanup failed: {e}")

        # For file-based caches, remove the directory/file
        if hasattr(cache, "_path"):
            path = cache._path
            if isinstance(path, (str, Path)):
                path = Path(path)
                if path.exists():
                    if path.is_dir():
                        shutil.rmtree(path, ignore_errors=True)
                    else:
                        path.unlink(missing_ok=True)

    except Exception as e:
        logger.warning(f"Cache cleanup failed: {e}")


def cleanup_database(database: Any) -> None:
    """
    Clean up a database instance.

    Args:
        database: Database instance to clean up
    """
    try:
        # Commit any pending transaction
        if hasattr(database, "in_transaction") and database.in_transaction():
            database.commit()

        # Use drop() for comprehensive cleanup
        if hasattr(database, "drop"):
            database.drop()

    except Exception as e:
        logger.warning(f"Database cleanup failed: {e}")

        # Try fallback cleanup methods
        try:
            provider = getattr(database, "dialect", None) or getattr(database, "_provider", None)
            db_type = getattr(database, "_db_type", None)
            database_path = getattr(database, "_database", None)

            if provider in ["pg", "mysql", "postgresql"]:
                # For external databases, try to clear instead of drop
                if hasattr(database, "clear"):
                    database.clear()
            elif db_type == "file" and database_path:
                # For file databases, try to remove the file directly
                if os.path.exists(database_path):
                    os.remove(database_path)
            else:
                # For in-memory, just close the connection
                if hasattr(database, "_conn") and database._conn is not None:
                    database.close()
        except Exception as fallback_e:
            logger.warning(f"Database fallback cleanup also failed: {fallback_e}")

    finally:
        # Final connection cleanup
        try:
            if hasattr(database, "_conn") and database._conn is not None:
                database.close()
        except Exception:
            pass


def cleanup_vdb(vdb: Any) -> None:
    """
    Clean up a vector database instance.

    Args:
        vdb: VectorDatabase instance to clean up
    """
    try:
        # Try to drop the vector database
        if hasattr(vdb, "drop"):
            vdb.drop()

        # For file-based VDBs, remove the directory
        if hasattr(vdb, "_database") and vdb._database:
            path = Path(vdb._database)
            if path.exists() and path.is_dir():
                shutil.rmtree(path, ignore_errors=True)

        # Close connection if available
        if hasattr(vdb, "close"):
            vdb.close()

    except Exception as e:
        logger.warning(f"VDB cleanup failed: {e}")


def cleanup_klstore(klstore: Any) -> None:
    """
    Clean up a KLStore instance.

    Args:
        klstore: KLStore instance to clean up
    """
    try:
        # Clear the KLStore
        if hasattr(klstore, "clear"):
            klstore.clear()

        # Flush any pending operations
        if hasattr(klstore, "flush"):
            klstore.flush()

        # Clean up the underlying storage
        if hasattr(klstore, "_storage"):
            storage = klstore._storage
            storage_class_name = storage.__class__.__name__

            if "Cache" in storage_class_name:
                cleanup_cache(storage)
            elif "Database" in storage_class_name or "DB" in storage_class_name:
                cleanup_database(storage)
            elif "Vector" in storage_class_name or "VDB" in storage_class_name:
                cleanup_vdb(storage)

    except Exception as e:
        logger.warning(f"KLStore cleanup failed: {e}")


def cleanup_klengine(klengine: Any) -> None:
    """
    Clean up a KLEngine instance.

    Args:
        klengine: KLEngine instance to clean up
    """
    try:
        # Clear the KLEngine
        if hasattr(klengine, "clear"):
            klengine.clear()

        # Flush any pending operations
        if hasattr(klengine, "flush"):
            klengine.flush()

        # Clean up the underlying storage
        if hasattr(klengine, "_storage"):
            cleanup_klstore(klengine._storage)

        # Clean up the index if separate
        if hasattr(klengine, "_index") and klengine._index is not None:
            index = klengine._index
            index_class_name = index.__class__.__name__

            if "Database" in index_class_name or "DB" in index_class_name:
                cleanup_database(index)
            elif "Vector" in index_class_name or "VDB" in index_class_name:
                cleanup_vdb(index)

    except Exception as e:
        logger.warning(f"KLEngine cleanup failed: {e}")


def cleanup_test_directories(base_dir: Path) -> None:
    """
    Clean up test directories recursively.

    Args:
        base_dir: Base directory to clean up
    """
    if base_dir.exists() and base_dir.is_dir():
        try:
            shutil.rmtree(base_dir, ignore_errors=True)
        except Exception as e:
            logger.warning(f"Failed to clean up test directory {base_dir}: {e}")
