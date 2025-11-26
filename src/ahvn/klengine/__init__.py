__all__ = [
    "BaseKLEngine",
    "FacetKLEngine",
    "DAACKLEngine",
    "VectorKLEngine",
    "MongoKLEngine",
    "facet_engine",
    "vector_engine",
    "mongo_engine",
    "daac_engine",
]

from .base import *
from ..utils.basic import lazy_getattr, lazy_import_submodules

_EXPORT_MAP = {
    "FacetKLEngine": ".facet_engine",
    "DAACKLEngine": ".daac_engine",
    "VectorKLEngine": ".vector_engine",
    "MongoKLEngine": ".mongo_engine",
}

_SUBMODULES = ["facet_engine", "vector_engine", "mongo_engine", "daac_engine"]


def __getattr__(name):
    mod = lazy_import_submodules(name, _SUBMODULES, __name__)
    if mod:
        return mod
    return lazy_getattr(name, _EXPORT_MAP, __name__)
