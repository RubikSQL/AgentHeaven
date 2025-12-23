import importlib

from .examples_utils import *


def __getattr__(name):
    if name == "autoi18n":
        return getattr(importlib.import_module(".autoi18n", __name__), name)
    if name == "autotask":
        return getattr(importlib.import_module(".autotask", __name__), name)
    if name == "autofunc":
        return getattr(importlib.import_module(".autofunc", __name__), name)
    if name == "autocode":
        return getattr(importlib.import_module(".autocode", __name__), name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
