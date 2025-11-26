import importlib


def __getattr__(name):
    if name in ("AhvnKLBase", "HEAVEN_KB", "_rebuild_heaven_kb"):
        return getattr(importlib.import_module(".ahvn_klbase", __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
