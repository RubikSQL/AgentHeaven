"""
Fixture infrastructure for JSON-based test configuration.

This package provides a unified approach to generating pytest fixtures
from declarative JSON configurations in tests.json.
"""

from .config_loader import TestConfigLoader
from .factory import UniversalFactory
from .parametrize import (
    generate_parametrize,
    minimal_cache_filter,
    minimal_db_filter,
    minimal_vdb_filter,
    minimal_mdb_filter,
    minimal_klstore_filter,
    minimal_klengine_filter,
    representative_cache_filter,
    representative_db_filter,
    representative_vdb_filter,
    representative_mdb_filter,
    representative_klstore_filter,
    representative_klengine_filter,
)
from .cleanup import cleanup_instance

__all__ = [
    "TestConfigLoader",
    "UniversalFactory",
    "generate_parametrize",
    "cleanup_instance",
    "minimal_cache_filter",
    "minimal_db_filter",
    "minimal_vdb_filter",
    "minimal_mdb_filter",
    "minimal_klstore_filter",
    "minimal_klengine_filter",
    "representative_cache_filter",
    "representative_db_filter",
    "representative_vdb_filter",
    "representative_mdb_filter",
    "representative_klstore_filter",
    "representative_klengine_filter",
]
