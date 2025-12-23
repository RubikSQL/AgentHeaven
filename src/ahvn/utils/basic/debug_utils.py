__all__ = [
    "value_match",
    "raise_mismatch",
    "error_str",
    "FunctionDeserializationError",
    "LLMError",
    "ToolError",
    "DatabaseError",
    "AutoFuncError",
    "DependencyError",
]

from .log_utils import get_logger

logger = get_logger(__name__)

from difflib import SequenceMatcher
from typing import Literal, Any, List, Optional, Tuple


def value_match(
    supported: List[Any],
    got: Any,
    thres: float = 0.3,
) -> List[Tuple[Any, float]]:
    """\
    Find similar values from a list of supported values, returning matches sorted by similarity score.

    Args:
        supported (List[Any]): A list of supported values.
        got (Any): The value to match against the supported list.
        thres (float): The minimum similarity threshold. Only matches with similarity >= thres are returned. Defaults to 0.3.

    Returns:
        List[Tuple[Any, float]]: A list of (value, score) tuples sorted by score descending.
            Only includes values with similarity >= thres.
    """

    def similarity(a: Any, b: Any) -> float:
        return SequenceMatcher(None, str(a), str(b)).ratio()

    scored = [(val, similarity(got, val)) for val in supported]
    filtered = [(val, score) for val, score in scored if score >= thres]
    return sorted(filtered, key=lambda x: x[1], reverse=True)


def raise_mismatch(
    supported: List[Any],
    got: Any,
    name: str = "value",
    mode: Literal["ignore", "match", "warn", "exit", "raise"] = "raise",
    comment: Optional[str] = None,
    thres: float = 0.3,
) -> str:
    """\
    Raise an error if the value is not in the list of supported values, suggesting the closest match.

    Args:
        supported (List[Any]): A list of supported values.
        got (Any): The value to check against the supported list.
        name (str): The name of the value for error messages. Defaults to 'value'.
        mode (Literal['ignore','match','warn','exit','raise']): The mode of handling the mismatch.
            - 'ignore': Do nothing.Directly returns the original value if no close match is found.
            - 'match': Do nothing. Directly returns the suggestion if a close match is found.
            - 'warn': Log a warning message. Returns the suggestion if a close match is found.
            - 'exit': Log an error message and exit the program with status 1.
            - 'raise': Raise a ValueError with the error message.
            Defaults to 'raise'.
        comment (Optional[str]): An optional comment to include in the error message. Defaults to None.
        thres (float): The threshold for similarity to consider a suggestion valid. Defaults to 0.3.

    Returns:
        str: The suggested value if a close match is found and mode is 'warn'. Otherwise, returns None.
            If `got` is in `supported`, does nothing and returns `got`.

    Raises:
        ValueError: If the value is not in the supported list and the mode is 'raise'.
        NotImplementedError: If an unknown mode is provided.
    """
    if got in supported:
        return got
    if mode == "ignore":
        return got

    matches = value_match(supported, got, thres=thres)
    suggestion = matches[0][0] if matches else None
    if mode == "match":
        return suggestion
    message = "\n".join(
        [
            msg
            for msg in [
                f"Unsupported {name} '{got}'.",
                f"Did you mean '{suggestion}'?" if suggestion else None,
                "Available options: " + (", ".join(f"'{opt}'" for opt in supported) if len(supported) > 0 else "none") + ".",
                f" {comment}" if comment else None,
            ]
            if msg is not None
        ]
    )
    if mode == "warn":
        logger.warning(message)
        return suggestion
    elif mode == "exit":
        logger.error(message)
        exit(1)
    elif mode == "raise":
        raise ValueError(message)
    else:
        raise_mismatch(["ignore", "warn", "exit", "raise"], got=mode, name="mode", mode="raise", thres=1.0)


import traceback


def error_str(err: Optional[Exception] = None, tb: Optional[bool] = True) -> str:
    """\
    Get a string representation of an error, optionally including the traceback.

    Args:
        err (Optional[Exception]): The exception to format. If None, returns None.
        tb (Optional[bool]): Whether to include the traceback in the output. Defaults to True.

    Returns:
        str: The formatted error string. Or None if `err` is None.
    """
    if err is None:
        return None
    if isinstance(err, str):
        return err.strip()
    if isinstance(err, Exception):
        return "".join(traceback.format_exception(type(err), err, err.__traceback__)).strip() if tb else str(err).strip()
    return str(err).strip()


class FunctionDeserializationError(Exception): ...


class LLMError(Exception): ...


class ToolError(Exception): ...


class DatabaseError(Exception): ...


class AutoFuncError(Exception): ...


class DependencyError(ImportError): ...
