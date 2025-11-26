from .vdb_utils import *

import typing

if typing.TYPE_CHECKING:
    from .types import *
    from .compiler import *
    from .base import *

__all__ = [
    # vdb_utils
    "parse_encoder_embedder",
    "resolve_vdb_config",
    # types
    "BaseVdbType",
    "VdbIdType",
    "VdbTextType",
    "VdbIntegerType",
    "VdbBooleanType",
    "VdbDurationType",
    "VdbTimestampType",
    "VdbJsonType",
    "VdbVectorType",
    "VdbTagsType",
    "VdbSynonymsType",
    "VdbRelatedType",
    "VdbAuthsType",
    # compiler
    "VectorCompiler",
    # base
    "VectorDatabase",
]


def __getattr__(name):
    if name in [
        "BaseVdbType",
        "VdbIdType",
        "VdbTextType",
        "VdbIntegerType",
        "VdbBooleanType",
        "VdbDurationType",
        "VdbTimestampType",
        "VdbJsonType",
        "VdbVectorType",
        "VdbTagsType",
        "VdbSynonymsType",
        "VdbRelatedType",
        "VdbAuthsType",
    ]:
        from . import types

        return getattr(types, name)

    if name == "VectorCompiler":
        from . import compiler

        return getattr(compiler, name)

    if name == "VectorDatabase":
        from . import base

        return getattr(base, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
