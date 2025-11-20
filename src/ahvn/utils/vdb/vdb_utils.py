"""Vector database utilities."""

__all__ = [
    "parse_encoder_embedder",
    "resolve_vdb_config",
]

from ..basic.config_utils import HEAVEN_CM
from ..basic.debug_utils import raise_mismatch
from ..basic.cmd_utils import cmd

from typing import List, Optional, Union, Callable, Tuple, Any
from copy import deepcopy
import os

from ...llm.base import LLM


def parse_encoder_embedder(
    encoder: Union[Callable[[Any], str], Tuple[Callable[[Any], str], Callable[[Any], str]]] = None,
    embedder: Optional[Union[str, Callable[[str], List[float]], Tuple[Callable[[str], List[float]], Callable[[str], List[float]]], "LLM"]] = None,
) -> Tuple[
    Tuple[Callable[[Any], str], Callable[[Any], str]],
    Tuple[Callable[[str], List[float]], Callable[[str], List[float]]],
    int,
    int,
]:
    """Parse encoder and embedder parameters into standardized tuples and detect dimensions.

    Args:
        encoder: Required encoder function or tuple (k_encoder, q_encoder).
        embedder: Optional embedder function, tuple (k_embedder, q_embedder), or LLM instance.

    Returns:
        Tuple of (encoder_tuple, embedder_tuple, k_dim, q_dim) where:
        - encoder_tuple: (k_encoder, q_encoder) functions
        - embedder_tuple: (k_embedder, q_embedder) functions or LLM instances
        - k_dim: dimension of key embedder
        - q_dim: dimension of query embedder

    Raises:
        ValueError: If encoder is None or dimensions cannot be determined.
    """
    if encoder is None:
        encoder = (None, None)
    if isinstance(encoder, tuple):
        k_encoder, q_encoder = encoder
    else:
        k_encoder = encoder
        q_encoder = encoder
    if k_encoder is None:

        def default_k_encoder(kl: Any) -> str:
            return kl.text()

        k_encoder = default_k_encoder
    if q_encoder is None:

        def default_q_encoder(query: Any) -> str:
            return str(query).strip()

        q_encoder = default_q_encoder

    if embedder is None:
        embedder = "embedder"
    if embedder is False:
        embedder = None
    if isinstance(embedder, str):
        embedder = LLM(preset=embedder)

    if isinstance(embedder, tuple):
        k_embedder, q_embedder = embedder
    else:
        k_embedder = embedder
        q_embedder = embedder

    if isinstance(k_embedder, LLM):
        k_dim = k_embedder.dim
        k_embedder = k_embedder.embed
    elif k_embedder:
        k_dim = len(k_embedder("<TEST>"))
    else:
        k_dim = 0  # Fallback to 0 if no embedder
    if isinstance(q_embedder, LLM):
        q_dim = q_embedder.dim
        q_embedder = q_embedder.embed
    elif q_embedder:
        q_dim = len(q_embedder("<TEST>"))
    else:
        q_dim = 0  # Fallback to 0 if no embedder

    return (k_encoder, q_encoder), (k_embedder, q_embedder), k_dim, q_dim


def resolve_vdb_config(collection: str = None, provider: str = None, **kwargs):
    """Resolve vector database configuration from parameters and environment variables.

    Args:
        collection: Optional collection name.
        provider: Optional vector database provider name.
        **kwargs: Additional configuration parameters.
    Returns:
        Resolved configuration dictionary.
    """

    vdb_config = HEAVEN_CM.get("vdb", dict())
    providers_config = vdb_config.get("providers", dict())
    default_provider = vdb_config.get("default_provider", "sqlite")
    default_args = vdb_config.get("default_args", dict())

    args = dict()
    args.update(deepcopy(default_args))

    # Resolve provider parameters
    if not provider:
        provider = default_provider
    if provider and (provider not in providers_config):
        raise_mismatch(providers_config, got=provider, name="vector database provider")
    provider_config = providers_config.get(provider, dict())
    args.update(deepcopy(provider_config))

    # Resolve custom kwargs
    if collection:
        args["collection"] = collection
    args.update(kwargs)

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
