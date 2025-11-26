__all__ = [
    "BaseKLStore",
    "CacheKLStore",
    "CascadeKLStore",
    "DatabaseKLStore",
    "MongoKLStore",
    "VectorKLStore",
    "cache_store",
    "cascade_store",
    "db_store",
    "mdb_store",
    "vdb_store",
]

from .base import *
from ..utils.basic import lazy_getattr, lazy_import_submodules

_EXPORT_MAP = {
    "CacheKLStore": ".cache_store",
    "CascadeKLStore": ".cascade_store",
    "DatabaseKLStore": ".db_store",
    "MongoKLStore": ".mdb_store",
    "VectorKLStore": ".vdb_store",
}

_SUBMODULES = ["cache_store", "cascade_store", "db_store", "mdb_store", "vdb_store"]


def __getattr__(name):
    mod = lazy_import_submodules(name, _SUBMODULES, __name__)
    if mod:
        return mod
    return lazy_getattr(name, _EXPORT_MAP, __name__)
