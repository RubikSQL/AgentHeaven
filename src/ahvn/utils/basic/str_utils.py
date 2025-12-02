"""\
String manipulation and text processing utilities for AgentHeaven.
"""

__all__ = [
    "truncate",
    "value_repr",
    "omission_list",
    "markdown_symbol",
    "line_numbered",
    "indent",
    "is_delimiter",
    "normalize_text",
    "generate_ngrams",
    "asymmetric_jaccard_score",
    "resolve_match_conflicts",
]

import string
import textwrap
from typing import Any, Union, Set, List, Optional, Tuple
from ..deps import deps


def truncate(s: str, cutoff: int = -1) -> str:
    """\
    Truncate a string if it exceeds the specified cutoff length.

    Args:
        s (str): The string to truncate.
        cutoff (int): Maximum length before truncation. Defaults to -1, meaning no cutoff.

    Returns:
        str: Truncated string if it exceeds cutoff, otherwise the original string.
    """
    if cutoff < 0 or len(s) <= cutoff:
        return s
    return s[: cutoff - 4] + "..." + s[-1:]


def value_repr(value: Any, cutoff: int = -1, round_digits: int = 6) -> str:
    """\
    Format a value representation for display, truncating if too long.

    Args:
        value (Any): The value to represent.
        cutoff (int): Maximum length before truncation. Defaults to -1, meaning no cutoff.
        round_digits (int): Number of decimal places to round floats to.
            Only applied if the value is a float. Default is 6.

    Returns:
        str: Formatted value representation.
    """
    if isinstance(value, float):
        value = round(value, round_digits)
    value_repr_str = repr(value)
    return truncate(value_repr_str, cutoff=cutoff)


def omission_list(items: List, top: int = -1, bottom: int = 1) -> List:
    """\
    Cuts down a list by omitting middle items if it exceeds the specified limit.

    Args:
        items (List): The list of items.
        top (int): Number of items to keep from the start. Defaults to -1 (keep all).
        bottom (int): Number of items to keep from the end. Defaults to 1.
            Bottom is ignored if top is negative.
            Otherwise, total kept items = top + bottom + 1.

    Returns:
        List: The truncated list with middle items omitted if necessary.
    """
    max_items = -1 if top < 0 else top + bottom
    n = len(items)
    if max_items < 0 or n <= max_items:
        return items
    omitted_cnt = n - max_items
    return items[:top] + [f"... (omitting {omitted_cnt})"] + (items[-bottom:] if bottom > 0 else [])


def markdown_symbol(content: str):
    """\
    Generate a markdown code block symbol that does not conflict with the content.

    Args:
        content (str): The content to check for conflicts.

    Returns:
        str: A markdown code block symbol (e.g., "```", "````", etc.) that does not appear in the content.
    """
    symbol = "```"
    while symbol in content:
        symbol += "```"
    return symbol


def line_numbered(content: str, start: int = -1, window: Optional[Tuple[int, int]] = None) -> str:
    """\
    Adds line numbers to the given content starting from the specified number.

    Args:
        content (str): The content to be numbered.
        start (int): The starting line number. If negative, no line numbers
            are added. Defaults to -1.
        window (Optional[Tuple[int, int]]): A tuple specifying the (start, end)
            line numbers to include. If None, includes all lines. Defaults to None.

    Returns:
        str: The content with line numbers added.
    """
    if not isinstance(content, str):
        content = str(content)
    lines = content.splitlines()
    if start >= 0:
        contents = [f"({i:4d})  {line}" for i, line in enumerate(lines, start=start)]
    else:
        contents = [f"{line}" for i, line in enumerate(lines)]
    return "\n".join(contents[window[0] : window[1]] if window is not None else contents)


def indent(s: str, tab: Union[int, str] = 4, **kwargs) -> str:
    """\
    Indent a string by a specified number of spaces or a tab character.

    Args:
        s (str): The string to indent.
        tab (int or str, optional): The number of spaces or a tab character to use for indentation. Defaults to 4 spaces.
        **kwargs: Additional keyword arguments are ignored.

    Returns:
        str: The indented string.
    """
    return textwrap.indent(s, prefix=(" " * tab if isinstance(tab, int) else tab), **kwargs)


def is_delimiter(char: str) -> bool:
    """\
    Check if a character is a word boundary breaker.

    Args:
        char (str): The character to check.

    Returns:
        bool: True if the character is whitespace or punctuation, False otherwise.
    """
    return (char in string.whitespace) or (char in string.punctuation)


_spacy_nlp = None


def normalize_text(text: str) -> str:
    """\
    Normalize text through tokenization, stop word removal, lemmatization, and lowercasing.

    Args:
        text (str): The input text to normalize.

    Returns:
        str: The normalized text with tokens separated by spaces.
    """
    global _spacy_nlp
    if _spacy_nlp is None:  # Lazy Import
        deps.require("spacy", "text normalization")
        import spacy

        _spacy_nlp = spacy.load("en_core_web_sm", disable=["parser", "ner"])
    return " ".join(
        [
            token.lemma_.strip()
            for token in _spacy_nlp(text.lower().replace("_", "-").replace("-", " "))
            if not token.is_stop and not token.is_punct and token.lemma_.strip()
        ]
    )


def generate_ngrams(tokens: list, n: int) -> Set[str]:
    """\
    Generate n-grams from a list of tokens.

    Args:
        tokens (list): List of tokens to generate n-grams from.
        n (int): Maximum n-gram size.

    Returns:
        Set[str]: Set of n-grams with sizes from 1 to n.
    """
    return {" ".join(tokens[i : i + k]) for k in range(1, n + 1) for i in range(len(tokens) - k + 1)}


def asymmetric_jaccard_score(query: str, doc: str, ngram: int = 6) -> float:
    """\
    Calculate asymmetric Jaccard containment score between query and document.

    Args:
        query (str): The query text.
        doc (str): The document text.
        ngram (int, optional): Maximum n-gram size. Defaults to 6.

    Returns:
        float: Containment score between 0.0 and 1.0.
    """
    q = generate_ngrams(normalize_text(query).split(), n=ngram)
    d = generate_ngrams(normalize_text(doc).split(), n=ngram)
    if not q:
        return 1.0
    return len(q.intersection(d)) / len(q)


def resolve_match_conflicts(
    results: list,
    conflict: str = "overlap",
    query_length: int = 0,
    inverse: bool = False,
) -> list:
    """\
    Resolve overlapping matches in search results based on conflict strategy.

    This utility function filters overlapping text spans when multiple entities match
    at the same or overlapping positions in a query string. It operates on search results
    that contain match position information.

    Args:
        results (list): List of result dictionaries. Each dictionary must contain:
            - 'id': Entity identifier
            - 'matches': List of (start, end) tuples representing match positions in the query
        conflict (str, optional): Strategy for handling overlapping matches. Options:
            - "overlap": Keep all matches including overlapping ones (no filtering)
            - "longest": Keep only the longest match for any overlapping set
            - "longest_distinct": Allow multiple entities to have overlapping matches
                                as long as they are the longest matches
            Defaults to "overlap".
        query_length (int, optional): Length of the query string. Required for "longest"
            and "longest_distinct" strategies when inverse=True. Defaults to 0.
        inverse (bool, optional): Whether the matches were computed on reversed strings.
            Affects the sorting and comparison logic. Defaults to False.

    Returns:
        list: Filtered list of result dictionaries with the same structure as input,
            where each result's 'matches' list has been filtered according to the
            conflict resolution strategy.

    Examples:
        >>> results = [
        ...     {'id': 1, 'matches': [(0, 5), (10, 15), (22, 27), (32, 37)]},
        ...     {'id': 2, 'matches': [(2, 8), (12, 18), (21, 27), (32, 38)]}
        ... ]
        >>> resolve_match_conflicts(results, conflict="longest", query_length=40)
        [{'id': 1, 'matches': [(0, 5), (10, 15)]}, {'id': 2, 'matches': [(21, 27), (32, 38)]}]
    """
    if conflict == "overlap":
        return results

    # Extract all intervals with their entity IDs
    intervals = [(r["id"], start, end) for r in results for start, end in r["matches"]]

    # Sort intervals: for inverse mode, sort by end descending then start ascending
    # For normal mode, sort by start ascending then end descending
    sorted_intervals = sorted(intervals, key=(lambda x: (-x[2], x[1], x[0])) if inverse else (lambda x: (x[1], -x[2], x[0])))

    if conflict == "longest":
        filtered = _resolve_longest_conflicts(sorted_intervals, query_length, inverse)
    elif conflict == "longest_distinct":
        filtered = _resolve_longest_distinct_conflicts(sorted_intervals, query_length, inverse)
    else:
        return results

    results_mapping = {r["id"]: r for r in results}
    grouped_results = dict()
    for entity_id, start, end in filtered:
        if entity_id not in grouped_results:
            grouped_results[entity_id] = {"id": entity_id, "matches": []}
        grouped_results[entity_id]["matches"].append((start, end))

    return [results_mapping[result["id"]] | {"matches": sorted(result["matches"])} for result in grouped_results.values() if result["matches"]]


def _resolve_longest_conflicts(intervals: list, query_length: int, inverse: bool) -> list:
    """\
    Internal helper: Resolve conflicts using longest match strategy.

    Keeps only the left-longest non-overlapping matches.
    Specifically, if (l1, r1) and (l2, r2) overlaps:
        if l1 < l2: keep (l1, r1)
        if l1 > l2: keep (l2, r2)
        if l1 == l2: keep the longer one
        if l1 == r1 and l2 == r2: keep either one (arbitrary, the one with smaller id in practice)
    When inverse=True, the logic is applied in reverse order (right-longest)
    """
    filtered = []
    prev = query_length if inverse else 0

    for entity_id, start, end in intervals:
        if (end <= prev) if inverse else (start >= prev):
            filtered.append((entity_id, start, end))
            prev = start if inverse else end

    return filtered


def _resolve_longest_distinct_conflicts(intervals: list, query_length: int, inverse: bool) -> list:
    """\
    Internal helper: Resolve conflicts using longest distinct match strategy.

    Keeps only the left-longest non-overlapping matches.
    Specifically, if (l1, r1) and (l2, r2) overlaps:
        if l1 < l2: keep (l1, r1)
        if l1 > l2: keep (l2, r2)
        if l1 == l2: keep the longer one
        if l1 == r1 and l2 == r2: keep both
    When inverse=True, the logic is applied in reverse order (right-longest)
    """
    filtered = []
    prev = query_length if inverse else 0
    selected = (-1, -1)

    for entity_id, start, end in intervals:
        if ((end <= prev) if inverse else (start >= prev)) or (start, end) == selected:
            filtered.append((entity_id, start, end))
            prev = start if inverse else end
            selected = (start, end)

    return filtered
