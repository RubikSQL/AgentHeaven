__all__ = [
    "valid_tag",
    "tag_s",
    "tag_v",
    "tag_t",
    "ptags",
    "gtags",
    "TagOperator",
    "TagFilter",
    "has_tag",
    "has_related",
    "next_ver",
]

from ..utils.basic.misc_utils import lflat

from collections import defaultdict
from typing import Dict, Iterable, Union, Literal, Optional, Tuple, Any


# import re
# _tag_regex = r"\[([^:\]]+):(.*?)\]"
def valid_tag(tag: str):
    if not isinstance(tag, str):
        raise TypeError(f"Tag must be a string, got {type(tag)}")
    tag = tag.strip()
    # if not re.match(_tag_regex, tag):
    if not (tag.startswith("[") and tag.endswith("]") and (":" in tag[1:-1])):
        raise ValueError(f"Tag '{tag}' does not match required format '[slot:value]'")
    return tag


def tag_s(tag: str):
    """\
    Return the slot (key) from a tag string.

    A tag is expected to be in the format ``"[slot:value]"``. This helper
    extracts and returns the slot portion.

    Args:
        tag (str): Tag in the format ``"[slot:value]"``.

    Returns:
        str: The slot part (text before the first ``":"``).
    """
    tag = valid_tag(tag)
    return tag[1:-1].split(":", 1)[0]


def tag_v(tag: str):
    """\
    Return the value part from a tag string.

    Args:
        tag (str): Tag in the format ``"[slot:value]"``.

    Returns:
        str: The value part (text after the first ``":"``).
    """
    tag = valid_tag(tag)
    return tag[1:-1].split(":", 1)[1]


def tag_t(tag: str):
    """\
    Split a tag string into ``(slot, value)``.

    Args:
        tag (str): Tag in the format ``"[slot:value]"``.

    Returns:
        List[str]: A sequence of two strings: ``[slot, value]``.
    """
    tag = valid_tag(tag)
    return tag[1:-1].split(":", 1)


def ptags(**kwargs):
    """\
    Create formatted tag strings from keyword arguments.

    Values may be scalars or iterables; iterables are expanded into multiple tags; None values are skipped.

    Args:
        **kwargs: Keys will be used as tag slots, values provide
            the tag values. Example: ``TYPE=['doc','text'], LANG='en'``.

    Returns:
        Set[str]: A set of tag strings in the format ``"[SLOT:value]"``.
    """
    return set(
        lflat(([f"[{k}:{v}]" for v in t if v is not None] if isinstance(t, (list, tuple, set)) else [f"[{k}:{t}]"]) for k, t in kwargs.items() if t is not None)
    )


def gtags(tags: Iterable[str], **kwargs):
    """\
    Group tags by slot name and collect values.

    This converts a flat list/set of tag strings into a mapping from slot
    to set of values. Additional tags can be provided via the same
    keyword interface accepted by :func:`ptags`.

    Args:
        tags (Iterable[str]): Iterable of tag strings like ``"[slot:value]"``.
        **kwargs: Extra tags passed to :func:`ptags`.

    Returns:
        Dict[str, Set[str]]: Mapping from lowercase slot name to a set of values.
    """
    groups = defaultdict(set)
    for tag in tags:
        groups[tag_s(tag)].add(tag_v(tag))
    for tag in ptags(**kwargs):
        groups[tag_s(tag)].add(tag_v(tag))
    return dict(groups)


TagOperator = Union[
    Literal[
        "EXACT",
        "NONE_OF",
        "ANY_OF",
        "ANY_IF_EXISTS",
        "ONE_OF",
        "MANY_OF",
        "ALL_OF",
        "ALL_IN",
        "HAS_NONE",
        "HAS_ANY",
        "HAS_ONE",
        "HAS_MANY",
    ],
    int,
    float,
]
TagFilter = Dict[Literal["slot", "operator", "value"], Union[str, TagOperator, Optional[Union[Iterable, str, Any]]]]


def has_tag(
    tags: Iterable[str],
    slot: str,
    operator: TagOperator = "ANY_OF",
    value: Optional[Union[Iterable, str, Any]] = None,
):
    """\
    Check whether a collection of tags satisfies a condition for a slot.

    The function supports a variety of operators to express membership and
    set-based conditions. See the implementation for the full list of
    supported operators; common ones include ``ANY_OF``, ``ALL_OF``, and
    unary tests like ``HAS_NONE``.

    Args:
        tags (Iterable[str]): Iterable of tag strings, e.g. ``"[type:doc]"``.
        slot (str): Slot name to check (the left-hand part of a tag).
        operator (TagOperator): Operator describing the condition. Can be a
            textual operator (see module-level :data:`TagOperator`) or a
            numeric requirement (``int`` or ``float`` are treated specially).
        value (Optional[Union[Iterable, str, Any]]): Value(s) to compare
            against. Required for non-unary operators.

    Operators:
        "EXACT" or "==": Slot values exactly match the provided values (sets equal).
        "NONE_OF": No slot values match the provided values.
        "ANY_OF": At least one slot value matches the provided values.
        "ANY_IF_EXISTS": If the slot exists, at least one provided value matches; if slot missing, returns True.
        "ONE_OF": Exactly one slot value matches the provided values.
        "MANY_OF": At least two slot values match the provided values.
        "ALL_OF": All provided values are present in the slot values.
        "ALL_IN" or "IN": All slot values are included in the provided values.
        "HAS_NONE": Unary — slot has no values.
        "HAS_ANY": Unary — slot has at least one value.
        "HAS_ONE": Unary — slot has exactly one value.
        "HAS_MANY": Unary — slot has at least two values.
        int: Numeric operator meaning "at least N matching values".
        float: Jaccard similarity threshold (intersection/union >= threshold).

    Returns:
        bool: True when the condition holds for the provided tags, otherwise False.

    Raises:
        ValueError: If an unary operator is given a non-None ``value`` or when an
            unsupported operator is provided.
    """
    if isinstance(value, (list, tuple, set)):
        vals = set(str(v) for v in value)
    else:
        vals = set([str(value)])
    slot_vals = gtags(tags).get(slot, set())
    if (operator == "EXACT") or (operator == "=="):
        return (len(vals) == len(slot_vals)) and vals.issubset(slot_vals)
    if operator == "NONE_OF":
        return len(slot_vals.intersection(vals)) == 0
    if operator == "ANY_OF":
        return len(slot_vals.intersection(vals)) >= 1
    if operator == "ANY_IF_EXISTS":
        return (len(slot_vals) == 0) or (len(slot_vals.intersection(vals)) >= 1)
    if operator == "ONE_OF":
        return len(slot_vals.intersection(vals)) == 1
    if operator == "MANY_OF":
        return len(slot_vals.intersection(vals)) >= 2
    if operator == "ALL_OF":
        return len(slot_vals.intersection(vals)) == len(vals)
    if (operator == "ALL_IN") or (operator == "IN"):
        return len(slot_vals.intersection(vals)) == len(slot_vals)
    if operator == "HAS_NONE":
        if value is not None:
            raise ValueError("'HAS_NONE' is a unary operator, `value` must be set to `None`.")
        return len(slot_vals) == 0
    if operator == "HAS_ANY":
        if value is not None:
            raise ValueError("'HAS_ANY' is a unary operator, `value` must be set to `None`.")
        return len(slot_vals) >= 1
    if operator == "HAS_ONE":
        if value is not None:
            raise ValueError("'HAS_ONE' is a unary operator, `value` must be set to `None`.")
        return len(slot_vals) == 1
    if operator == "HAS_MANY":
        if value is not None:
            raise ValueError("'HAS_MANY' is a unary operator, `value` must be set to `None`.")
        return len(slot_vals) >= 2
    if isinstance(operator, int):
        return len(slot_vals.intersection(vals)) >= operator
    if isinstance(operator, float):
        # Jaccard similarity threshold between provided values and slot values
        return len(slot_vals.intersection(vals)) / len(slot_vals.union(vals)) >= operator
    raise ValueError(f"Unsupported operator: {operator}")


RelationFilter = Dict[
    Literal["subject_id", "relation", "object_id", "relation_id", "related_to_id"],
    Union[int, Iterable[int], str, Iterable[str]],
]


def has_related(
    related: Iterable[Tuple[int, str, int, Optional[int], Optional[Dict[str, Any]]]],
    subject_id: Optional[Union[int, Iterable[int]]] = None,
    relation: Optional[Union[str, Iterable[str]]] = None,
    object_id: Optional[Union[int, Iterable[int]]] = None,
    relation_id: Optional[Union[int, Iterable[int]]] = None,
    related_to_id: Optional[Union[int, Iterable[int]]] = None,
) -> bool:
    """\
    Return True when the given related tuples contain a matching relation.

    Each relation tuple is expected to be in the form
    ``(subject_id, relation, object_id, relation_id?, relation_resources?)``.

    Args:
        related (Iterable[Tuple[int, str, int, Optional[int], Optional[Dict]]]):
            Iterable of relation tuples to search.
        subject_id (Optional[Union[int, Iterable[int]]]): Filter for subject id(s).
        relation (Optional[Union[str, Iterable[str]]]): Filter for relation name(s).
        object_id (Optional[Union[int, Iterable[int]]]): Filter for object id(s).
        relation_id (Optional[Union[int, Iterable[int]]]): Filter for relation id(s).
        related_to_id (Optional[Union[int, Iterable[int]]]): If provided, the
            function matches relations where either the subject or object id is in
            this set.

    Returns:
        bool: True if at least one relation satisfies all provided filters.
    """
    if subject_id is not None:
        subject_id = set(int(v) for v in subject_id) if isinstance(subject_id, (list, tuple, set)) else {int(subject_id)}
    if relation is not None:
        relation = set(str(v) for v in relation) if isinstance(relation, (list, tuple, set)) else {str(relation)}
    if object_id is not None:
        object_id = set(int(v) for v in object_id) if isinstance(object_id, (list, tuple, set)) else {int(object_id)}
    if relation_id is not None:
        relation_id = set(int(v) for v in relation_id) if isinstance(relation_id, (list, tuple, set)) else {int(relation_id)}
    if related_to_id is not None:
        related_to_id = set(int(v) for v in related_to_id) if isinstance(related_to_id, (list, tuple, set)) else {int(related_to_id)}
    for _subject_id, _relation, _object_id, _relation_id, _ in related:
        if (subject_id is not None) and (_subject_id not in subject_id):
            continue
        if (relation is not None) and (_relation not in relation):
            continue
        if (object_id is not None) and (_object_id not in object_id):
            continue
        if (relation_id is not None) and (_relation_id not in relation_id):
            continue
        if (related_to_id is not None) and (_subject_id not in related_to_id) and (_object_id not in related_to_id):
            continue
        return True
    return False


def next_ver(version):
    """\
    Return the next version string by incrementing the last numeric part.

    If the last component of ``version`` is numeric it will be incremented by
    one. Otherwise a new numeric component ``"1"`` will be appended.

    Args:
        version (str): Current version string (for example ``"v1.2.3"`` or
            ``"v1.2.beta"``).

    Returns:
        str: New version string with the final numeric component incremented or
            appended.

    Examples:
        >>> next_ver('v1.2.3')
        'v1.2.4'
        >>> next_ver('v1.2.beta')
        'v1.2.beta.1'
    """
    versions = version.split(".")
    if versions[-1].isdigit():
        versions[-1] = str(int(versions[-1]) + 1)
    else:
        versions += ["1"]
    return ".".join(versions)
