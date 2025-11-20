"""
Mock embedder utilities for testing VDB and VectorKLStore without requiring actual LLM services.
"""

from typing import List, Union
from ahvn.utils.basic.rnd_utils import stable_rnd_vector
from ahvn.utils.basic.hash_utils import md5hash


def mock_encoder(obj) -> str:
    """
    Mock encoder that converts any object to a string representation.

    Args:
        obj: Any object to encode (BaseUKF, string, etc.)

    Returns:
        String representation of the object
    """
    if hasattr(obj, "content"):
        # For BaseUKF objects
        return f"{obj.name}: {obj.content}"
    else:
        # For plain strings
        return str(obj)


def mock_embedder(text: Union[str, List[str]], dim: int = 128) -> Union[List[float], List[List[float]]]:
    """
    Mock embedder that generates stable, deterministic vectors from text.

    Uses stable_rnd_vector to create reproducible embeddings where:
    - The same text always produces the same vector
    - Different texts produce different vectors
    - Vectors approximate real embedding behavior (major dimension + noise)

    Args:
        text: Text to embed (str) or list of texts to embed (List[str])
        dim: Embedding dimension (default 128)

    Returns:
        Normalized embedding vector for a single string, or list of vectors for a list of strings
    """
    # Handle list of strings
    if isinstance(text, list):
        return [mock_embedder(t, dim=dim) for t in text]

    # Handle single string
    # Hash the text to get an integer seed for stable_rnd_vector
    seed = md5hash(text)
    return stable_rnd_vector(seed, dim=dim)


def create_mock_encoder_embedder(dim: int = 128):
    """
    Create a tuple of (encoder, embedder) for mock testing.

    Args:
        dim: Embedding dimension

    Returns:
        Tuple of (encoder_func, embedder_func)
    """
    encoder = mock_encoder

    def embedder(text: Union[str, List[str]]) -> List[float]:
        return mock_embedder(text, dim=dim)

    return encoder, embedder
