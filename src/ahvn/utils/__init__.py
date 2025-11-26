from .basic import *
from .basic import lazy_getattr, lazy_import_submodules

from .klop import *

_EXPORT_MAP = {
    "Database": ".db",
    "SQLProcessor": ".db",
    "ExportableEntity": ".db",
    "DatabaseIdType": ".db",
    "DatabaseJsonType": ".db",
    "VectorDatabase": ".vdb",
    "VectorStore": ".vdb",
    "MongoDatabase": ".mdb",
    "autoi18n": ".exts",
    "autotask": ".exts",
    "autofunc": ".exts",
    "autocode": ".exts",
}

_SUBMODULES = ["db", "vdb", "mdb", "exts"]


def __getattr__(name):
    mod = lazy_import_submodules(name, _SUBMODULES, __name__)
    if mod:
        return mod
    return lazy_getattr(name, _EXPORT_MAP, __name__)
