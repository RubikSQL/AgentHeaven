"""\
Basic utilities for AgentHeaven.

This subpackage groups helpers for logging, colors, paths, files, configs,
serialization, hashing, templating, and small conveniences used across the project.
"""

import importlib
import datetime
from typing import *
from copy import deepcopy
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from collections import defaultdict

from .deps_utils import collect_exports, lazy_getattr

_SUBMODULES = [
    "cmd_utils",
    "color_utils",
    "config_utils",
    "debug_utils",
    "deps_utils",
    "file_utils",
    "func_utils",
    "hash_utils",
    "jinja_utils",
    "log_utils",
    "misc_utils",
    "parallel_utils",
    "parser_utils",
    "path_utils",
    "progress_utils",
    "request_utils",
    "rnd_utils",
    "serialize_utils",
    "str_utils",
    "type_utils",
]

_lazy_modules = collect_exports(_SUBMODULES, __name__)


def __getattr__(name):
    return lazy_getattr(name, _lazy_modules, __name__)


__all__ = list(_lazy_modules.keys()) + [
    "datetime",
    "deepcopy",
    "dataclass",
    "field",
    "ABC",
    "abstractmethod",
    "defaultdict",
    "Any",
    "Dict",
    "List",
    "Optional",
    "Union",
    "Tuple",
    "Type",
    "Callable",
    "Iterable",
    "Generator",
    "Literal",
]
