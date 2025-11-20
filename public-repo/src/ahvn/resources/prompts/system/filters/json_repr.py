from ahvn.utils.basic.serialize_utils import dumps_json
from typing import Any

JSON_REPR_CUTOFF_DEFAULT = 256
JSON_REPR_ROUND_DEFAULT = 6
JSON_REPR_INDENT_DEFAULT = 4


def json_repr(content: Any, cutoff: int = JSON_REPR_CUTOFF_DEFAULT, round_digits: int = JSON_REPR_ROUND_DEFAULT, indent: int = JSON_REPR_INDENT_DEFAULT) -> str:
    """\
    Returns a JSON representation of the value, truncated to the specified length.

    Args:
        content (Any): The value to be represented.
        cutoff (int): The maximum length of the string representation.
            If cutoff is negative, no truncation will be applied. Default is 256.
        round_digits (int): Number of decimal places to round floats to.
            Only applied if the value is a float. Default is 6.

    Returns:
        A string representation of the value, truncated if necessary.
    """
    if isinstance(content, float):
        content = round(content, round_digits)
    s = dumps_json(content, indent=indent)
    return s if len(s) <= cutoff or cutoff < 0 else s[: cutoff - 3] + "..."
