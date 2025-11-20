"""\
Hashing helpers used across AgentHeaven.
"""

__all__ = [
    "md5hash",
    "fmt_hash",
    "fmt_short_hash",
]

from .log_utils import get_logger

logger = get_logger(__name__)
from .serialize_utils import dumps_json

from hashlib import md5 as MD5
from typing import Any, Union


def _serialize(obj):
    """\
    Serialize objects deterministically for hashing.

    Functions are represented by their fully-qualified name; JSON-serializable
    objects are dumped with stable ordering; otherwise fallback to repr().
    """
    if obj is None:
        return None
    if callable(obj) and hasattr(obj, "__module__") and hasattr(obj, "__qualname__"):
        return f"{obj.__module__}.{obj.__qualname__}"
    try:
        return dumps_json(obj, sort_keys=True, indent=None)
    except Exception as e:
        logger.warning(f"Failed to JSON serialize object {obj}: {e}. Falling back to repr().")
    return repr(obj)


def md5hash(obj: Any, salt: Any = None, sep: str = "||") -> int:
    """\
    Generate an MD5 hash for the given object.

    Args:
        obj (Any): The object to hash.
        salt (Any, optional): An optional salt to add to the hash.
        sep (str, optional): Separator for concatenating serialized parts.

    Returns:
        int: The MD5 hash as an integer.
    """
    obj_repr, salt_repr = _serialize(obj), _serialize(salt)
    return int(MD5((f"{obj_repr}" if salt is None else f"{obj_repr}{sep}{salt_repr}").encode("utf-8")).hexdigest(), 16)


def fmt_hash(id: Union[str, int]) -> str:
    """\
    Format an `md5hash` ID integer as a zero-padded string.

    Args:
        id (int): The ID to format.

    Returns:
        str: The formatted ID string.
    """
    if id is None:
        return None
    if not isinstance(id, str):
        return f"{id:040d}"
    return str(id)


def fmt_short_hash(id: Union[str, int], length: int = 8) -> str:
    """\
    Format an `md5hash` ID integer as a short zero-padded string.

    Args:
        id (int): The ID to format.
        length (int, optional): The length of the short hash string.

    Returns:
        str: The formatted short hash string.
    """
    if id is None:
        return None
    if not isinstance(id, str):
        return f"{id % (10**length):0{length}d}"
    return str(id)[-length:]
