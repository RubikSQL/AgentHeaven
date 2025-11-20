__all__ = [
    "unique",
    "lflat",
    "counter_percentiles",
]

from typing import Iterable, List, Any, Dict, Union, Set


def unique(iterable: Iterable[Any], key=lambda x: x) -> List[Any]:
    """\
    Return a list of unique elements from an iterable, preserving order.

    Args:
        iterable (Iterable[Any]): The input iterable to filter for unique elements.
        key (callable, optional): A function to extract a comparison key from each element. Defaults to the identity function.

    Returns:
        List[Any]: A list containing only the unique elements from the input iterable.

    Examples:
        >>> unique([1, 2, 2, 3, 1])
        [1, 2, 3]
        >>> unique(['apple', 'banana', 'orange'], key=len)
        ['apple', 'banana']
    """
    seen, uni = set(), list()
    for item in iterable:
        k = key(item)
        if not (k in seen or seen.add(k)):
            uni.append(item)
    return uni


def lflat(iterable: Iterable[Iterable[Any]]) -> List[Any]:
    """\
    Flatten a nested iterable (2 levels deep) into a single list.

    Args:
        iterable (Iterable[Iterable[Any]]): The nested iterable to flatten.

    Returns:
        List[Any]: A flat list containing all elements from the nested iterable.

    Examples:
        >>> lflat([[1, 2], [3, 4]])
        [1, 2, 3, 4]
    """
    return [item for sublist in iterable for item in sublist]


def counter_percentiles(counter: Dict, percentiles: Set[Union[int, float]] = {0, 25, 50, 75, 100}) -> Dict[int, Any]:
    """\
    Calculate specified percentiles from a frequency counter.

    Args:
        counter (Dict): A dictionary where keys are values and values are their frequencies.
        percentiles (List[Union[int, float]]): List of percentiles to calculate. Defaults to [0, 25, 50, 75, 100].

    Returns:
        Dict[int, Any]: A dictionary mapping each requested percentile to its corresponding value.

    Examples:
        >>> counter = {1: 2, 2: 3, 3: 5}
        >>> counter_percentiles(counter, [0, 50, 100])
        {0: 1, 50: 2, 100: 3}
    """
    total = sum(counter.values())
    sorted_items = sorted(counter.items(), key=lambda x: x[0])
    results, accum, idx = [(p, None) for p in sorted(percentiles)], 0, 0
    for value, freq in sorted_items:
        accum += freq
        while idx < len(results) and accum / total >= results[idx][0] / 100.0:
            results[idx] = (results[idx][0], value)
            idx += 1
    return dict(results)
