"""\
MongoDB configuration utilities for AgentHeaven.

This module provides functions to parse and resolve MongoDB configurations
similar to how database configurations are handled. It supports multiple MongoDB
providers and generates PyMongo-ready configurations with connection strings
and parameters.
"""

__all__ = [
    "resolve_mdb_config",
]

from ..basic.log_utils import get_logger
from ..basic.config_utils import HEAVEN_CM
from ..basic.cmd_utils import cmd

import os
from typing import Dict, Any, Optional
from copy import deepcopy

logger = get_logger(__name__)


def resolve_mdb_config(database: Optional[str] = None, collection: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """\
    Compile a MongoDB configuration dictionary based on the following order of priority:
    1. kwargs
    2. global configuration
    When a parameter is specified in multiple places, the one with the highest priority is used.

    Args:
        database (str, optional): The database name to use.
        collection (str, optional): The collection name to use.
        **kwargs: Additional parameters to override in the configuration.

    Returns:
        Dict[str, Any]: The resolved MongoDB configuration dictionary.

    Example:
        >>> config = resolve_mdb_config(collection="my_collection")
        >>> config = resolve_mdb_config(host="192.168.1.100")
        >>> config = resolve_mdb_config(connection_string="mongodb://localhost:27017/mydb")
    """
    mdb_config = HEAVEN_CM.get("mdb", dict())
    default_args = mdb_config.get("default_args", dict())

    args = dict()
    args.update(deepcopy(default_args))

    # Resolve custom kwargs
    if database:
        args["database"] = database
    if collection:
        args["collection"] = collection
    args.update(deepcopy(kwargs))

    # Resolve environment variables
    for k, v in args.items():
        if isinstance(v, str) and v.startswith("<") and v.endswith(">"):
            env_var = v[1:-1]
            if env_var in os.environ:
                args[k] = os.environ[env_var]

    # Resolve environment commands (e.g., ${whoami})
    for k, v in args.items():
        if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
            env_val = cmd(v[2:-1], include="stdout")
            if env_val:
                args[k] = env_val.strip()

    # Remove None values
    args = {k: v for k, v in args.items() if (v is not None)}

    return args
