"""\
Cache backends for AgentHeaven.

Includes in-memory, on-disk, and JSON-file caches, plus a no-op cache.
"""

__all__ = [
    "CacheEntry",
    "BaseCache",
    "NoCache",
    "DiskCache",
    "JsonCache",
    "InMemCache",
    "CallbackCache",
    "DatabaseCache",
    "MongoCache",
]

from .base import CacheEntry, BaseCache
from .no_cache import NoCache
from .disk_cache import DiskCache
from .json_cache import JsonCache
from .in_mem_cache import InMemCache
from .callback_cache import CallbackCache

from ..utils.basic import lazy_getattr

_EXPORT_MAP = {
    "DatabaseCache": ".db_cache",
    "MongoCache": ".mongo_cache",
}


def __getattr__(name):
    return lazy_getattr(name, _EXPORT_MAP, __name__)
