__all__ = [
    "Message",
    "Messages",
    "LLMChunk",
    "LLMResponse",
    "LLM",
    "gather_assistant_message",
    "resolve_llm_config",
]

from ..utils.basic.config_utils import encrypt_config, hpj
from ..utils.basic.misc_utils import unique
from ..utils.basic.request_utils import NetworkProxy
from ..utils.basic.debug_utils import error_str
from .llm_utils import *
from ..cache.base import BaseCache
from ..cache.no_cache import NoCache
from ..cache.disk_cache import DiskCache

logger = get_logger(__name__)

import inspect

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from typing import Generator, AsyncGenerator, Any, Dict, List, Optional, Union, Iterable
from dataclasses import dataclass, field
from copy import deepcopy


@dataclass
class LLMChunk:
    """\
    A response object that holds various formats of LLM output.
    """

    chunks: List[Dict[str, Any]] = field(default_factory=list)
    think: str = field(default="")
    text: str = field(default="")
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    content: str = field(default="")
    delta_think: str = field(default="")
    delta_text: str = field(default="")
    delta_tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    delta_content: str = field(default="")
    think_begin_token: str = field(default="<think>\n")
    think_end_token: str = field(default="\n</think>\n")
    _thinking: Optional[bool] = None

    def __getitem__(self, key: str) -> Any:
        """\
        Get item by key, allowing for dict-like access.
    """
        return getattr(self, key, default=None)

    def __add__(self, other: Union["LLMChunk", Dict]) -> "LLMChunk":
        """\
        Combine two LLMChunk objects.
    """
        self.delta_think = ""
        self.delta_text = ""
        self.delta_tool_calls = list()
        self.delta_content = ""
        for chunk in other.chunks if isinstance(other, LLMChunk) else [other]:
            self.chunks.append(chunk)
            delta_think = chunk.get("think", "")
            delta_text = chunk.get("text", "")
            delta_tool_calls = chunk.get("tool_calls", list())
            delta_content = ""
            if delta_think:
                if self._thinking is None:
                    self._thinking = True
                    delta_content += self.think_begin_token
                delta_content += delta_think
            if delta_text:
                if self._thinking is True:
                    self._thinking = False
                    delta_content += self.think_end_token
                delta_content += delta_text
            self.delta_think += delta_think
            self.delta_text += delta_text
            self.delta_tool_calls += delta_tool_calls
            self.delta_content += delta_content
        self.think += self.delta_think
        self.text += self.delta_text
        self.tool_calls += self.delta_tool_calls
        self.content += self.delta_content
        return self

    def to_message(self) -> Dict[str, Any]:
        """\
        Convert the response to a message format.
    """
        return {
            "role": "assistant",
            "content": self.text,
            "tool_calls": self.tool_calls,
        }

    def to_message_delta(self) -> Dict[str, Any]:
        """\
        Convert the response to a message delta format.
    """
        return {
            "role": "assistant",
            "content": self.delta_text,
            "tool_calls": self.delta_tool_calls,
        }

    def to_dict(self) -> Dict[str, Any]:
        """\
        Convert the response to a dictionary format.
    """
        return {
            "text": self.text,
            "think": self.think,
            "tool_calls": self.tool_calls,
            "content": self.content,
            "message": self.to_message(),
        }

    def to_dict_delta(self) -> Dict[str, Any]:
        """\
        Convert the response to a delta format.
    """
        return {
            "text": self.delta_text,
            "think": self.delta_think,
            "tool_calls": self.delta_tool_calls,
            "content": self.delta_content,
            "message": self.to_message_delta(),
        }


def _llm_response_formatting(
    delta: Dict[str, Any], include: Optional[Iterable[str]], messages: List[Dict[str, Any]] = None, reduce: bool = True
) -> Union[Dict[str, Any], str]:
    messages = messages or list()
    formatted_delta = {k: (delta[k] if k != "messages" else deepcopy(messages) + [delta["message"]]) for k in include}
    return formatted_delta if len(include) > 1 and reduce else formatted_delta[include[0]]


def gather_assistant_message(messages: List[Dict]):
    """\
    Gather assistant messages (returned by `LLMChunk.to_message()`) from a list of message dictionaries.

    Args:
        messages (List[Dict]): A list of message dictionaries to gather.

    Returns:
        Dict[str, Any]: A dictionary containing the gathered assistant message.
    """
    gathered = {"role": "assistant", "content": "", "tool_calls": list()}
    for message in messages:
        gathered["content"] += message.get("content", "")
        gathered["tool_calls"].extend(message.get("tool_calls", list()))
    if not message.get("tool_calls"):
        del gathered["tool_calls"]
    return gathered


LLMResponse = Union[str, Dict[str, Any], List[Union[str, Dict[str, Any]]]]


class LLM(object):
    """\
    High-level chat LLM client with retry, caching, proxy, and streaming support.

    This class wraps a litellm-compatible chat API and provides two access modes:
    - stream: incremental (delta) results as they arrive
    - oracle: full (final) result collected from the stream

    Key features:
    - Retry: automatic retries via tenacity on retryable exceptions.
    - Caching: memoizes successful results keyed by all request inputs and a user-defined `name`. Excluded keys can be configured via `cache_exclude`.
    - Streaming-first: always uses `stream=True` under the hood for stability; `oracle` aggregates the stream.
    - Proxies: optional `http_proxy` and `https_proxy` support per-request.
    - Flexible messages: accepts multiple message formats and normalizes them.
    - Output shaping: `include` and `reduce` control what is returned and whether to flatten lists.

    Parameters:
        preset (str | None): Named preset from configuration (if supported by resolve_llm_config).
        model (str | None): Model identifier (e.g., "gpt-4o"). Overrides preset when provided.
        provider (str | None): Provider name used by the underlying client.
        cache (Union[bool, str, BaseCache] | None): Cache implementation. Defaults to True.
            If True, uses DiskCache with the default cache directory ("core.cache_path").
            If a string is provided, it is treated as the path for DiskCache.
            If None/False, uses NoCache (no caching).
        cache_exclude (list[str] | None): Keys to exclude from cache key construction.
        name (str | None): Logical name for this LLM instance. Used to namespace the cache. Defaults to "llm".
        **kwargs: Additional provider/client config (e.g., temperature, top_p, n, tools, tool_choice, http_proxy, https_proxy, and any litellm client options).
            These act as defaults and can be overridden per call.

    Notes:
        - Caching: Only successful executions are cached. The cache key includes the normalized messages,
            the full effective configuration, and `name`, minus any keys listed in `cache_exclude`.
        - Set `name` differently for semantically distinct use-cases to avoid cache collisions.
    """

    def __init__(
        self,
        preset: str = None,
        model: str = None,
        provider: str = None,
        cache: Union[bool, str, "BaseCache"] = True,
        cache_exclude: Optional[List[str]] = None,
        name: Optional[str] = None,
        **kwargs,
    ):
        super().__init__()
        self.name = name or "llm"
        self.config = resolve_llm_config(preset=preset, model=model, provider=provider, **kwargs)
        if (cache is None) or (cache is False):
            self.cache = NoCache()
        elif cache is True:
            self.cache = DiskCache(path=hpj(HEAVEN_CM.get("core.cache_path"), "llm_default"))
        elif isinstance(cache, str):
            self.cache = DiskCache(path=hpj(cache))
        else:
            self.cache = cache
        _cache_exclude = set(HEAVEN_CM.get("llm.cache_exclude_keys", list())) if cache_exclude is None else set(cache_exclude)
        self.cache.add_exclude(_cache_exclude)
        self._dim = None

    def _get_retry(self):
        retry_config = HEAVEN_CM.get("llm.retry", dict())
        max_attempts = retry_config.get("max_attempts", 3)
        wait_multiplier = retry_config.get("multiplier", 1)
        wait_max = retry_config.get("max", 60)
        reraise = retry_config.get("reraise", True)
        return retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=wait_multiplier, max=wait_max),
            retry=retry_if_exception_type(tuple(LITELLM_RETRYABLE_EXCEPTION_TYPES)),
            reraise=reraise,
        )

    def _cached_stream(self, **inputs) -> Generator[Any, None, None]:
        @self._get_retry()
        def vanilla_stream(**inputs) -> Generator[Any, None, None]:
            for chunk in litellm.completion(**inputs):
                if not chunk.choices:  # Handle empty responses
                    raise ValueError("Empty response from LLM API")
                yield [
                    {
                        "think": getattr(choice.delta, "reasoning_content", None) or "",
                        "text": getattr(choice.delta, "content", None) or "",
                        "tool_calls": getattr(choice.delta, "tool_calls", None) or list(),
                    }
                    for choice in chunk.choices
                ]
            return

        @self.cache.memoize(name=self.name)
        def cached_vanilla_stream(**inputs) -> Generator[Any, None, None]:
            yield from vanilla_stream(**inputs)

        yield from cached_vanilla_stream(**inputs)
        return

    async def _cached_astream(self, **inputs) -> AsyncGenerator[Any, None]:
        @self._get_retry()
        async def vanilla_astream(**inputs) -> AsyncGenerator[Any, None]:
            stream_resp = await litellm.acompletion(**inputs)

            try:
                if hasattr(stream_resp, "__aiter__"):
                    async for chunk in stream_resp:
                        if not chunk.choices:  # Handle empty responses
                            raise ValueError("Empty response from LLM API")
                        yield [
                            {
                                "think": getattr(choice.delta, "reasoning_content", None) or "",
                                "text": getattr(choice.delta, "content", None) or "",
                                "tool_calls": getattr(choice.delta, "tool_calls", None) or list(),
                            }
                            for choice in chunk.choices
                        ]
                elif hasattr(stream_resp, "__iter__"):
                    for chunk in stream_resp:
                        if not chunk.choices:
                            raise ValueError("Empty response from LLM API")
                        yield [
                            {
                                "think": getattr(choice.delta, "reasoning_content", None) or "",
                                "text": getattr(choice.delta, "content", None) or "",
                                "tool_calls": getattr(choice.delta, "tool_calls", None) or list(),
                            }
                            for choice in chunk.choices
                        ]
                else:
                    raise TypeError(f"Unsupported async streaming response type: {type(stream_resp)}")
            finally:
                closer = getattr(stream_resp, "aclose", None)
                if callable(closer):
                    maybe = closer()
                    if inspect.isawaitable(maybe):
                        await maybe
                else:
                    closer = getattr(stream_resp, "close", None)
                    if callable(closer):
                        closer()
            return

        @self.cache.memoize(name=self.name)
        async def cached_vanilla_astream(**inputs) -> AsyncGenerator[Any, None]:
            async for chunk in vanilla_astream(**inputs):
                yield chunk
            return

        async for chunk in cached_vanilla_astream(**inputs):
            yield chunk
        return

    def _cached_embed(self, batch: List[str], **kwargs) -> List[List[float]]:
        @self._get_retry()
        def vanilla_embed(batch: List[str], **kwargs) -> List[List[float]]:
            empty = [i for i, text in enumerate(batch) if not text]
            non_empty_batch = [text for i, text in enumerate(batch) if i not in empty]
            if not non_empty_batch:
                return [self.embed_empty for _ in batch]
            embeddings = litellm.embedding(input=non_empty_batch, **kwargs).data
            return [self.embed_empty if i in empty else embeddings.pop(0)["embedding"] for i in range(len(batch))]

        @self.cache.batch_memoize(name=self.name)
        def cached_vanilla_embed(batch: List[str], **kwargs) -> List[List[float]]:
            return vanilla_embed(batch, **kwargs)

        return cached_vanilla_embed(batch, **kwargs)

    async def _cached_aembed(self, batch: List[str], **kwargs) -> List[List[float]]:
        @self._get_retry()
        async def vanilla_aembed(batch: List[str], **kwargs) -> List[List[float]]:
            empty = [i for i, text in enumerate(batch) if not text]
            non_empty_batch = [text for i, text in enumerate(batch) if i not in empty]
            if not non_empty_batch:
                return [self.embed_empty for _ in batch]
            embeddings_resp = await litellm.aembedding(input=non_empty_batch, **kwargs)
            embeddings = embeddings_resp.data
            return [self.embed_empty if i in empty else embeddings.pop(0)["embedding"] for i in range(len(batch))]

        @self.cache.batch_memoize(name=self.name)
        async def cached_vanilla_aembed(batch: List[str], **kwargs) -> List[List[float]]:
            return await vanilla_aembed(batch, **kwargs)

        return await cached_vanilla_aembed(batch, **kwargs)

    def _validate_include(self, include: Optional[Union[str, List[str]]] = None, stream: bool = True) -> List[str]:
        include = include or ["text"]
        if isinstance(include, str):
            include = [include]
        include = unique(include)
        if stream and ("messages" in include):
            raise ValueError("Return mode 'messages' is not supported for streaming requests, use `oracle` instead.")
        if not len(include):
            raise ValueError("Include list must not be empty.")
        supported = ["text", "think", "tool_calls", "content", "message", "messages"]
        for item in include:
            raise_mismatch(supported, got=item, thres=1.0)
        return include

    def _validate_config(self, messages: Messages, **kwargs):
        return {"n": 1} | deepcopy(self.config) | deepcopy(kwargs) | {"messages": messages} | {"stream": True}

    def stream(
        self,
        messages: Messages,
        include: Optional[Union[str, List[str]]] = None,
        verbose: bool = False,
        reduce: bool = True,
        **kwargs,
    ) -> Generator[LLMResponse, None, None]:
        """\
        Stream LLM responses (deltas) for the given messages.

        Features:
        - Retry: automatic retries for transient failures.
        - Caching: memoizes successful runs keyed by inputs and `name`.
        - Streaming-first: uses `stream=True` for stability; yields deltas as they arrive.
        - Proxies: supports `http_proxy` and `https_proxy` in kwargs.
        - Flexible input: accepts multiple message formats and normalizes them.
        - Output shaping: control returned fields with `include` and flattening with `reduce`.

        Args:
            messages: Conversation content, normalized by ``format_messages``:
                1) str -> treated as a single user message
                2) list:
                    - litellm.Message -> converted via json()
                    - str -> treated as user message
                    - dict -> used as-is and must include "role"
                If a dict contains "tool_calls", its "function.arguments" is JSON-encoded when needed.
            include: Fields to include in each streamed delta. Can be a str or list[str].
                Allowed: "text", "think", "tool_calls", "content", "message".
                Note: "messages" is NOT supported here (use ``oracle`` for that).
                Default: ["text"].
            verbose: If True, logs the resolved request config.
            reduce: If True, auto-reduce output:
                - When n == 1, returns a single item instead of a list of choices.
                - When len(include) == 1, returns a single value instead of a dict.
            **kwargs: Per-call overrides for LLM config (e.g., temperature, top_p, n, tools, http_proxy, https_proxy, etc.).

        Yields:
            LLMResponse:
            - A list when n > 1 or reduce == False.
            - A single item when n == 1 and reduce == True:
                - dict if len(include) > 1 or reduce == False
                - single value if len(include) == 1 and reduce == True

        Raises:
            ValueError: if `include` is empty or contains unsupported fields (e.g., "messages").
        """
        formatted_messages = format_messages(messages)
        include = self._validate_include(include=include, stream=True)
        config = self._validate_config(messages=formatted_messages, **kwargs)

        with NetworkProxy(
            http_proxy=config.pop("http_proxy", None),
            https_proxy=config.pop("https_proxy", None),
        ):
            if verbose:
                logger.info(f"HTTP  Proxy: {os.environ.get('HTTP_PROXY')}")
                logger.info(f"HTTPS Proxy: {os.environ.get('HTTPS_PROXY')}")
                logger.info(f"Request: {encrypt_config(config)}")
            n = config.get("n", 1)
            responses = [LLMChunk() for _ in range(n)]
            for chunk in self._cached_stream(**config):
                deltas = list()
                for i, choice in enumerate(chunk):
                    responses[i] += choice
                    deltas.append(_llm_response_formatting(delta=responses[i].to_dict_delta(), include=include, reduce=reduce))
                yield deltas[0] if n == 1 and reduce else deltas
            return

    async def astream(
        self,
        messages: Messages,
        include: Optional[Union[str, List[str]]] = None,
        verbose: bool = False,
        reduce: bool = True,
        **kwargs,
    ) -> AsyncGenerator[LLMResponse, None]:
        """\
        Asynchronously stream LLM responses (deltas) for the given messages.

        Mirrors :meth:`stream` but returns an async generator suitable for async workflows.

        Args:
            messages: Conversation content, normalized by ``format_messages`` (see ``stream`` for formats).
            include: Fields to include in each streamed delta. Can be a str or list[str]. Defaults to ["text"].
            verbose: If True, logs the resolved request config.
            reduce: If True, auto-reduce output (same semantics as ``stream``).
            **kwargs: Per-call overrides for LLM config (e.g., temperature, top_p, n, tools, proxy settings, etc.).

        Yields:
            LLMResponse: Matches the shape documented in :meth:`stream` with async iteration semantics.

        Raises:
            ValueError: if ``include`` is empty or contains unsupported fields (e.g., "messages").
        """
        formatted_messages = format_messages(messages)
        include = self._validate_include(include=include, stream=True)
        config = self._validate_config(messages=formatted_messages, **kwargs)

        with NetworkProxy(
            http_proxy=config.pop("http_proxy", None),
            https_proxy=config.pop("https_proxy", None),
        ):
            if verbose:
                logger.info(f"HTTP  Proxy: {os.environ.get('HTTP_PROXY')}")
                logger.info(f"HTTPS Proxy: {os.environ.get('HTTPS_PROXY')}")
                logger.info(f"Request: {encrypt_config(config)}")
            n = config.get("n", 1)
            responses = [LLMChunk() for _ in range(n)]
            async for chunk in self._cached_astream(**config):
                deltas = list()
                for i, choice in enumerate(chunk):
                    responses[i] += choice
                    deltas.append(_llm_response_formatting(delta=responses[i].to_dict_delta(), include=include, reduce=reduce))
                yield deltas[0] if n == 1 and reduce else deltas
            return

    def oracle(
        self,
        messages: Messages,
        include: Optional[Iterable[str]] = None,
        verbose: bool = False,
        reduce: bool = True,
        **kwargs,
    ) -> LLMResponse:
        """\
        Get the final LLM response for the given messages (aggregated from a stream).

        Features:
        - Retry: automatic retries for transient failures.
        - Caching: memoizes successful runs keyed by inputs and `name`.
        - Streaming-first: uses `stream=True` under the hood and aggregates the result.
        - Proxies: supports `http_proxy` and `https_proxy` in kwargs.
        - Flexible input: accepts multiple message formats and normalizes them.
        - Output shaping: control returned fields with `include` and flattening with `reduce`.

        Args:
            messages: Conversation content, normalized by ``format_messages``:
                1) str -> treated as a single user message
                2) list:
                    - litellm.Message -> converted via json()
                    - str -> treated as user message
                    - dict -> used as-is and must include "role"
                If a dict contains "tool_calls", its "function.arguments" is JSON-encoded when needed.
            include: Fields to include in the final result. Can be a str or list[str].
                Allowed: "text", "think", "tool_calls", "content", "message", "messages".
                Note: "messages" (the full dialog) is only supported here.
                Default: ["text"].
            verbose: If True, logs the resolved request config.
            reduce: If True, auto-reduce output:
                - When n == 1, returns a single item instead of a list of choices.
                - When len(include) == 1, returns a single value instead of a dict.
            **kwargs: Per-call overrides for LLM config (e.g., temperature, top_p, n, tools, http_proxy, https_proxy, etc.).

        Returns:
            LLMResponse:
            - A list when n > 1 or reduce == False.
            - A single item when n == 1 and reduce == True:
                - dict if len(include) > 1 or reduce == False
                - single value if len(include) == 1 and reduce == True

        Raises:
            ValueError: if `include` is empty or contains unsupported fields.
        """
        formatted_messages = format_messages(messages)
        include = self._validate_include(include=include, stream=False)
        config = self._validate_config(messages=formatted_messages, **kwargs)

        with NetworkProxy(
            http_proxy=config.pop("http_proxy", None),
            https_proxy=config.pop("https_proxy", None),
        ):
            if verbose:
                logger.info(f"HTTP  Proxy: {os.environ.get('HTTP_PROXY')}")
                logger.info(f"HTTPS Proxy: {os.environ.get('HTTPS_PROXY')}")
                logger.info(f"Request: {encrypt_config(config)}")
            n = config.get("n", 1)
            responses = [LLMChunk() for _ in range(n)]
            for chunk in self._cached_stream(**config):
                for i, choice in enumerate(chunk):
                    responses[i] += choice
            results = [_llm_response_formatting(responses[i].to_dict(), include=include, messages=formatted_messages, reduce=reduce) for i in range(n)]
            return results[0] if n == 1 and reduce else results

    async def aoracle(
        self,
        messages: Messages,
        include: Optional[Iterable[str]] = None,
        verbose: bool = False,
        reduce: bool = True,
        **kwargs,
    ) -> LLMResponse:
        """\
        Asynchronously retrieve the final LLM response (aggregated from the async stream).

        Mirrors :meth:`oracle` and shares its configuration, caching, and reduction semantics, but awaits async streaming.
        """
        formatted_messages = format_messages(messages)
        include = self._validate_include(include=include, stream=False)
        config = self._validate_config(messages=formatted_messages, **kwargs)

        with NetworkProxy(
            http_proxy=config.pop("http_proxy", None),
            https_proxy=config.pop("https_proxy", None),
        ):
            if verbose:
                logger.info(f"HTTP  Proxy: {os.environ.get('HTTP_PROXY')}")
                logger.info(f"HTTPS Proxy: {os.environ.get('HTTPS_PROXY')}")
                logger.info(f"Request: {encrypt_config(config)}")
            n = config.get("n", 1)
            responses = [LLMChunk() for _ in range(n)]
            async for chunk in self._cached_astream(**config):
                for i, choice in enumerate(chunk):
                    responses[i] += choice
            results = [_llm_response_formatting(responses[i].to_dict(), include=include, messages=formatted_messages, reduce=reduce) for i in range(n)]
            return results[0] if n == 1 and reduce else results

    def embed(self, inputs: Union[str, List[str]], verbose: bool = False, **kwargs) -> List[List[float]]:
        """\
        Get embeddings for the given inputs.

        Args:
            inputs: A single string or a list of strings to embed.
            verbose: If True, logs the resolved request config.
            **kwargs: Additional parameters for the embedding request.

        Returns:
            List[List[float]]: A list of embeddings, one for each input string.
        """
        if isinstance(inputs, str):
            inputs = [inputs]
            single = True
        else:
            single = False
        config = deepcopy(self.config) | deepcopy(kwargs)
        with NetworkProxy(
            http_proxy=config.pop("http_proxy", None),
            https_proxy=config.pop("https_proxy", None),
        ):
            if verbose:
                logger.info(f"HTTP  Proxy: {os.environ.get('HTTP_PROXY')}")
                logger.info(f"HTTPS Proxy: {os.environ.get('HTTPS_PROXY')}")
                logger.info(f"Request Args: {encrypt_config(config)}\nInputs:\n" + "\n".join(f"- {input}" for input in inputs))
            results = self._cached_embed(batch=inputs, **config)
            return results[0] if single else results

    async def aembed(self, inputs: Union[str, List[str]], verbose: bool = False, **kwargs) -> List[List[float]]:
        """\
        Get embeddings for the given inputs asynchronously.

        Provides parity with :meth:`embed` using `litellm.aembedding` under the hood while respecting caching behavior.
        """
        if isinstance(inputs, str):
            inputs = [inputs]
            single = True
        else:
            single = False
        config = deepcopy(self.config) | deepcopy(kwargs)
        with NetworkProxy(
            http_proxy=config.pop("http_proxy", None),
            https_proxy=config.pop("https_proxy", None),
        ):
            if verbose:
                logger.info(f"HTTP  Proxy: {os.environ.get('HTTP_PROXY')}")
                logger.info(f"HTTPS Proxy: {os.environ.get('HTTPS_PROXY')}")
                logger.info(f"Request Args: {encrypt_config(config)}\nInputs:\n" + "\n".join(f"- {input}" for input in inputs))
            results = await self._cached_aembed(batch=inputs, **config)
            return results[0] if single else results

    @property
    def dim(self):
        """\
        Get the dimensionality of the embeddings produced by this LLM.
        This is determined by making a test embedding call (i.e., "<TEST>").

        Warning:
            Due to efficiency considerations, this is only computed once and cached.
            If the LLM config is edited after the first call (which is not recommended), the result may be incorrect.

        Returns:
            int: The dimensionality of the embeddings.

        Raises:
            ValueError: if the embedding dimension cannot be determined.
        """
        if self._dim is not None:
            return self._dim
        try:
            test_embed = self.embed("<TEST>", verbose=False)
            if test_embed and isinstance(test_embed, list):
                self._dim = len(test_embed)
                return self._dim
            raise ValueError(f"Unexpected embedding format. This LLM may not support embeddings (got: {test_embed})")
        except Exception as e:
            raise ValueError(f"Failed to determine embedding. This LLM may not support embeddings (got error: {error_str(e)})")

    @property
    def embed_empty(self) -> List[float]:
        """\
        Get a fixed embedding vector for empty strings.

        This is a simple heuristic embedding consisting of a 1 followed by zeros,
        with the length equal to the LLM's embedding dimensionality.

        Returns:
            List[float]: The embedding vector for an empty string.
        """
        return [1.0] + [0.0] * (self.dim - 1)
