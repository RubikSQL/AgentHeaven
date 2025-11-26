from .db_utils import *

import typing

if typing.TYPE_CHECKING:
    from .types import *
    from .compiler import *
    from .base import *

__all__ = [
    # db_utils
    "resolve_db_config",
    "create_database_engine",
    "create_database",
    "split_sqls",
    "transpile_sql",
    "load_builtin_sql",
    "SQLProcessor",
    # types
    "ExportableEntity",
    "DatabaseIdType",
    "DatabaseTextType",
    "DatabaseIntegerType",
    "DatabaseBooleanType",
    "DatabaseDurationType",
    "DatabaseTimestampType",
    "DatabaseJsonType",
    "DatabaseNfType",
    "DatabaseVectorType",
    # compiler
    "SQLCompiler",
    # base
    "SQLResponse",
    "SQLErrorResponse",
    "DatabaseErrorHandler",
    "Database",
    "table_display",
]


def __getattr__(name):
    if name in [
        "ExportableEntity",
        "DatabaseIdType",
        "DatabaseTextType",
        "DatabaseIntegerType",
        "DatabaseBooleanType",
        "DatabaseDurationType",
        "DatabaseTimestampType",
        "DatabaseJsonType",
        "DatabaseNfType",
        "DatabaseVectorType",
    ]:
        from . import types

        return getattr(types, name)

    if name == "SQLCompiler":
        from . import compiler

        return getattr(compiler, name)

    if name in [
        "SQLResponse",
        "SQLErrorResponse",
        "DatabaseErrorHandler",
        "Database",
        "table_display",
    ]:
        from . import base

        return getattr(base, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
