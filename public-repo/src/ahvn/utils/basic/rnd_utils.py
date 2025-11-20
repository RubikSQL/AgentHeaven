"""\
Random utilities with stable seeding that don't interfere with global random state.
"""

__all__ = [
    "stable_rnd",
    "stable_rndint",
    "stable_shuffle",
    "stable_split",
    "stable_sample",
    "stable_rnd_vector",
]

import heapq
import random
from typing import Iterable, List, Any, Tuple, Optional
from .hash_utils import md5hash


def stable_rnd(seed: Optional[int] = 42) -> float:
    """\
    Generate a random float in [0.0, 1.0) without affecting the global random state.

    Args:
        seed (int, optional): Seed for deterministic random. Default is 42.
            If None, uses no salt (unstable). Nevertheless, it is strongly recommended
            to pass in a non-null `seed` value to ensure stability.

    Returns:
        float: Random float in [0.0, 1.0).
    """
    current_state = random.getstate()
    if seed is not None:
        random.seed(seed)
    result = random.random()
    random.setstate(current_state)
    return result


def stable_rndint(min: int, max: int, seed: Optional[int] = 42) -> int:
    """\
    Generate a random integer between min and max (inclusive) without affecting the global random state.

    Args:
        min (int): Minimum value (inclusive).
        max (int): Maximum value (inclusive).
        seed (int, optional): Seed for deterministic random. Default is 42.
            If None, uses no salt (unstable). Nevertheless, it is strongly recommended
            to pass in a non-null `seed` value to ensure stability.

    Returns:
        int: Random integer in the specified range.
    """
    current_state = random.getstate()
    if seed is not None:
        random.seed(seed)
    result = random.randint(min, max)
    random.setstate(current_state)
    return result


def stable_shuffle(seq: Iterable[Any], inplace: bool = False, seed: Optional[int] = 42) -> List[Any]:
    """\
    Shuffle a sequence without affecting the global random state.

    Args:
        seq (Iterable[Any]): The sequence to shuffle.
        inplace (bool, optional): If True, shuffle the input sequence in place
            (only works if seq is a mutable sequence). Default is False.
        seed (int, optional): Seed for deterministic shuffling. Default is 42.
            If None, uses no salt (unstable). Nevertheless, it is strongly recommended
            to pass in a non-null `seed` value to ensure stability.

    Returns:
        List[Any]: A new shuffled list containing the elements from seq.
    """
    if inplace and isinstance(seq, list):
        result = seq
    else:
        result = [s for s in seq]
    current_state = random.getstate()
    if seed is not None:
        random.seed(seed)
    random.shuffle(result)
    random.setstate(current_state)
    return result


def stable_split(seq: Iterable[Any], r: float = 0.10, seed: Optional[int] = 42) -> Tuple[List[Any], List[Any]]:
    """\
    Split a sequence into two parts based on a stable hash-based selection.

    This function creates a stable split that is resilient to adding/removing items.
    Items are selected for the first group based on their hash values, ensuring
    that the same items are consistently selected even when the sequence changes.

    It is worth addressing that the actual ratio of the split may not be exactly `r`
    due to the discrete nature of item selection based on hash values. However,
    over large datasets, the ratio should approximate `r`.
    To get an exact ratio/count, consider using `stable_sample` instead.

    Args:
        seq (Iterable[Any]): The sequence to split.
        r (float, optional): Ratio for the first group (default: 0.10 for 10%).
        seed (int, optional): Seed for deterministic splitting. Default is 42.
            If None, uses no salt (unstable). Nevertheless, it is strongly recommended
            to pass in a non-null `seed` value to ensure stability.

    Returns:
        Tuple[List[Any], List[Any]]: A tuple containing (selected_items, remaining_items).
    """
    if r == 0:
        return list(), [s for s in seq]
    P = 1061109589
    smaller, larger = list(), list()
    for item in seq:
        if md5hash(item, salt=seed) % P <= (P - 1) * r:
            smaller.append(item)
        else:
            larger.append(item)
    return smaller, larger


def stable_sample(seq: Iterable[Any], n: int, seed: Optional[int] = 42) -> List[Any]:
    """\
    Sample n elements without replacement in a stable manner using min n of hash values.

    This function creates a stable sample that is resilient to adding/removing items.
    Items are selected based on their hash values, ensuring that the same items are
    consistently selected even when the sequence changes, as long as n remains the same.

    Args:
        seq (Iterable[Any]): The sequence to sample from.
        n (int): Number of elements to sample.
        seed (int, optional): Seed for deterministic sampling. Default is 42.
            If None, uses no salt (unstable). Nevertheless, it is strongly recommended
            to pass in a non-null `seed` value to ensure stability.

    Returns:
        List[Any]: A list containing the sampled elements.
    """
    if n <= 0:
        return list()
    if n >= len(seq):
        return [s for s in seq]
    P = 1061109589
    mapping = {md5hash(item, salt=seed) % P: item for item in seq}
    return [mapping[h] for h in heapq.nsmallest(n, mapping.keys())]


def stable_rnd_vector(seed: Optional[int] = 42, dim: int = 384, major_ratio: float = 0.7) -> List[float]:
    """\
    Generate a stable random vector with a major value on a hashed dimension.

    This function creates a deterministic embedding-like vector where:
    - One dimension (determined by hashing the seed) has a major value
    - Other dimensions have small random values
    - The entire vector is normalized via softmax then L2 normalization to unit length

    This two-stage normalization (softmax followed by L2) better approximates the
    distribution of real embeddings compared to direct L2 normalization.

    This is useful for creating mock embeddings in tests where you need
    deterministic but varied vectors that approximate the behavior of real embeddings.

    Args:
        seed (int, optional): Seed value for deterministic generation. Default is 42.
            If None, uses 42 as default to ensure stability.
        dim (int, optional): Dimensionality of the vector. Default is 384
            (common embedding dimension).
        major_ratio (float, optional): Approximate ratio of the major dimension
            before normalization. Default is 0.7. The major dimension will have
            this value while others have small random values, then the whole
            vector is normalized via softmax + L2.

    Returns:
        List[float]: A normalized vector of length `dim` with unit L2 norm.

    Example:
        >>> vec1 = stable_rnd_vector(seed=123, dim=5)
        >>> vec2 = stable_rnd_vector(seed=123, dim=5)
        >>> vec1 == vec2  # Same seed produces same vector
        True
        >>> vec3 = stable_rnd_vector(seed=456, dim=5)
        >>> vec1 != vec3  # Different seed produces different vector
        True
    """
    import math

    # Use 42 as default seed if None provided
    if seed is None:
        seed = 42

    # Hash the seed to determine the major dimension
    hash_val = md5hash(seed)
    major_dim = hash_val % dim

    # Save current random state
    current_state = random.getstate()

    # Use hash as seed for reproducibility
    random.seed(hash_val)

    # Generate small random values for all dimensions
    vector = [random.uniform(0.01, 0.1) for _ in range(dim)]

    # Set the major dimension to a larger value
    vector[major_dim] = major_ratio

    # Apply softmax for initial normalization
    max_val = max(vector)
    exp_vector = [math.exp(x - max_val) for x in vector]  # Subtract max for numerical stability
    exp_sum = sum(exp_vector)
    softmax_vector = [x / exp_sum for x in exp_vector]

    # Apply L2 normalization to unit length
    magnitude = sum(x * x for x in softmax_vector) ** 0.5
    normalized = [x / magnitude for x in softmax_vector]

    # Restore random state
    random.setstate(current_state)

    return normalized
