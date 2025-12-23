__all__ = [
    "Message",
    "Messages",
    "LLMResponse",
    "LLM",
    "LLMIncludeType",
    "exec_tool_calls",
    "gather_assistant_message",
    "gather_stream",
    "resolve_llm_config",
    "format_messages",
]

from ..utils.basic.config_utils import encrypt_config, hpj
from ..utils.basic.misc_utils import unique
from ..utils.basic.request_utils import NetworkProxy
from ..utils.basic.debug_utils import error_str
from ..utils.basic.serialize_utils import loads_json, escape_json
from .llm_utils import *
from ..cache.base import BaseCache
from ..cache.no_cache import NoCache
from ..cache.disk_cache import DiskCache
from ..tool.base import ToolSpec

logger = get_logger(__name__)

import inspect
import json

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from typing import Generator, AsyncGenerator, Any, Dict, List, Optional, Union, Iterable, Literal
from dataclasses import dataclass, field
from copy import deepcopy


def _normalize_tool_call_delta(tool_call) -> Dict[str, Any]:
    """\
    Normalize a tool call delta object to a dict format.
    Handles both dict and litellm ChoiceDeltaToolCall objects.
    """
    if isinstance(tool_call, dict):
        return tool_call
    # Handle litellm ChoiceDeltaToolCall objects
    result = {
        "index": getattr(tool_call, "index", None),
        "id": getattr(tool_call, "id", None),
        "type": getattr(tool_call, "type", "function"),
    }
    func = getattr(tool_call, "function", None)
    if func:
        result["function"] = {
            "name": getattr(func, "name", None),
            "arguments": getattr(func, "arguments", "") or "",
        }
    return result


def _merge_tool_call_deltas(accumulated: List[Dict[str, Any]], deltas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """\
    Merge incremental tool call deltas into accumulated tool calls by index.
    """
    for delta in deltas:
        idx = delta.get("index", None) or (len(accumulated) - bool(delta.get("function", {}).get("name") is None))
        # Extend the list if necessary
        while idx >= len(accumulated):
            accumulated.append({"id": None, "type": "function", "function": {"name": "", "arguments": ""}})
        # Merge delta into accumulated
        if delta.get("id"):
            accumulated[idx]["id"] = delta["id"]
        if delta.get("type"):
            accumulated[idx]["type"] = delta["type"]
        if "function" in delta:
            func_delta = delta["function"]
            if func_delta.get("name"):
                accumulated[idx]["function"]["name"] = func_delta["name"]
            if func_delta.get("arguments"):
                accumulated[idx]["function"]["arguments"] = (accumulated[idx]["function"].get("arguments") or "") + func_delta["arguments"]
    return accumulated


def _normalize_tools(tools: Optional[List[Union[Dict, "ToolSpec"]]]) -> tuple:
    """\
    Normalize a list of tools to (jsonschema_list, toolspec_dict).

    Args:
        tools: List of tools, each can be a ToolSpec or a jsonschema dict.

    Returns:
        tuple: (jsonschema_list for LLM API, toolspec_dict mapping name->ToolSpec for execution)
    """
    if not tools:
        return [], {}
    jsonschema_list = []
    toolspec_dict = {}
    for tool in tools:
        if isinstance(tool, ToolSpec):
            jsonschema_list.append(tool.to_jsonschema())
            toolspec_dict[tool.binded.name] = tool
        elif isinstance(tool, dict):
            jsonschema_list.append(tool)
            # Extract name from jsonschema format
            name = tool.get("function", {}).get("name") or tool.get("name")
            if name:
                toolspec_dict[name] = None  # No ToolSpec available for execution
        else:
            raise TypeError(f"Tool must be ToolSpec or dict, got {type(tool)}")
    return jsonschema_list, toolspec_dict


def exec_tool_calls(tool_calls: List[Dict], toolspec_dict: Dict[str, Optional["ToolSpec"]]) -> tuple:
    """\
    Execute tool calls and return standardized tool messages/results.

    Compatibility:
    - Accepts tool calls with or without a ``function`` layer (e.g., ``{"name": "foo", "arguments": "{}"}``).
    - Missing or empty ``id`` defaults to an empty string.
    - ``arguments`` may be a dict or a JSON string; non-dict inputs are parsed via ``json.loads`` with graceful errors.

    Args:
        tool_calls: List of tool call dicts from LLM responses (raw or parsed).
        toolspec_dict: Mapping from tool name to ``ToolSpec`` (or None if not available).

    Returns:
        tuple: (tool_messages, tool_results)
            - tool_messages: List of tool message dicts in OpenAI format for conversation continuation.
            - tool_results: List of result content strings (just the returned values).

    Raises:
        ValueError: If a tool name is missing or the ToolSpec is unavailable.
    """

    tool_messages = []
    tool_results = []
    for tc in tool_calls:
        tc = tc or dict()
        func_info = tc.get("function") if isinstance(tc.get("function"), dict) else dict()
        name = (func_info.get("name") or tc.get("name") or "").strip()
        tool_call_id = tc.get("id") or ""
        args_raw = func_info.get("arguments") if func_info else tc.get("arguments", "{}")

        if not name:
            raise ValueError("Tool call missing function name.")

        toolspec = toolspec_dict.get(name)
        if toolspec is None:
            raise ValueError(f"Cannot execute tool '{name}': no ToolSpec available. " "tool_messages/tool_results requires all tools to be ToolSpec instances.")

        parse_error = None
        if isinstance(args_raw, dict):
            args = args_raw
        else:
            raw_str = args_raw if args_raw is not None else "{}"
            try:
                args = json.loads(raw_str)
            except Exception as exc:
                parse_error = f"Failed to parse arguments '{raw_str}' for tool '{name}': {exc}."
                args = dict()

        if parse_error:
            content = parse_error
        else:
            try:
                result = toolspec(**args)
                content = result
            except Exception as exc:
                content = f"Error executing tool '{name}': {exc}."

        content_str = str(content)
        tool_messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "name": name,
                "content": content_str,
            }
        )
        tool_results.append(content_str)

    return tool_messages, tool_results


def repair_tool_call(tool_call: Dict[str, Any], toolspec_dict: Dict[str, Any]) -> Dict[str, Any]:
    """\
    Repair a tool call by filling in missing fields using the ToolSpec.

    Args:
        tool_call: The tool call dict to repair.
        toolspec_dict: Mapping from tool name to ToolSpec.

    Returns:
        The repaired tool call dict.
    """
    tool_name = tool_call.get("function", {}).get("name")
    if tool_name not in toolspec_dict:
        tool_name = raise_mismatch(supported=list(toolspec_dict.keys()), got=tool_name, mode="match", thres=0.01)
    if tool_name not in toolspec_dict:
        raise ValueError(f"Cannot repair tool call for unknown tool '{tool_name}'.")
    toolspec = toolspec_dict[tool_name]
    args = list(toolspec.params)
    arguments = tool_call.get("function", {}).get("arguments", "{}")
    repaired_arguments = escape_json(arguments, args=args, indent=None)
    repaired_tool_call = deepcopy(tool_call)
    repaired_tool_call["function"]["name"] = tool_name
    repaired_tool_call["function"]["arguments"] = repaired_arguments
    return repaired_tool_call


@dataclass
class _LLMChunk:
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

    def __add__(self, other: Union["_LLMChunk", Dict]) -> "_LLMChunk":
        """\
        Combine two _LLMChunk objects.
    """
        self.delta_think = ""
        self.delta_text = ""
        self.delta_tool_calls = list()
        self.delta_content = ""
        for chunk in other.chunks if isinstance(other, _LLMChunk) else [other]:
            self.chunks.append(chunk)
            delta_think = chunk.get("think", "")
            delta_text = chunk.get("text", "")
            raw_tool_calls = chunk.get("tool_calls", list())
            # Normalize and merge tool_call deltas
            delta_tool_calls = [_normalize_tool_call_delta(tc) for tc in raw_tool_calls]
            _merge_tool_call_deltas(self.tool_calls, delta_tool_calls)
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
            self.delta_tool_calls = delta_tool_calls  # Store normalized deltas
            self.delta_content += delta_content
        self.think += self.delta_think
        self.text += self.delta_text
        # Note: tool_calls are merged incrementally, not appended
        self.content += self.delta_content
        return self

    def to_message(self) -> Dict[str, Any]:
        """\
        Convert the response to a message format.
    """
        return {
            "role": "assistant",
            "content": self.text,
        } | ({"tool_calls": self.tool_calls} if self.tool_calls else {})

    def to_message_delta(self) -> Dict[str, Any]:
        """\
        Convert the response to a message delta format.
    """
        return {
            "role": "assistant",
            "content": self.delta_text,
        } | ({"tool_calls": self.delta_tool_calls} if self.delta_tool_calls else {})

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


LLMIncludeType = Literal["text", "think", "tool_calls", "content", "message", "structured", "tool_messages", "tool_results", "delta_messages", "messages"]
_LLM_INCLUDES = ["text", "think", "tool_calls", "content", "message", "structured", "tool_messages", "tool_results", "delta_messages", "messages"]
_LLM_TEXT_INCLUDES = ["text", "think", "content"]
_LLM_LIST_INCLUDES = ["tool_calls", "tool_messages", "tool_results", "delta_messages", "messages"]
_LLM_STREAM_INCLUDES = ["text", "think", "content", "message"]


def _llm_response_formatting(
    delta: Dict[str, Any], include: List[LLMIncludeType], messages: List[Dict[str, Any]] = None, reduce: bool = True
) -> Union[Dict[str, Any], str, List]:
    """\
    Format the LLM response delta according to include fields and reduce settings.

    Args:
        delta: The response delta dict containing fields like text, think, tool_calls, tool_messages, tool_results, etc.
        include: Fields to include in the output.
        messages: Optional messages list for "messages" field construction.
        reduce: If True and len(include)==1, return the single value instead of dict.

    Returns:
        Formatted response - either a dict, single value, or list depending on include and reduce.
    """
    messages = messages or list()
    formatted_delta = {}
    for k in include:
        if k == "messages":
            if delta.get("messages") is not None:
                formatted_delta[k] = delta["messages"]
            else:
                formatted_delta[k] = (
                    deepcopy(messages)
                    + (delta["gathered_message"] if delta.get("gathered_message") else list())
                    + (delta["tool_messages"] if delta.get("tool_messages") else list())
                )
        elif k == "delta_messages":
            if delta.get("delta_messages") is not None:
                formatted_delta[k] = delta["delta_messages"]
            else:
                formatted_delta[k] = ([delta["gathered_message"]] if delta.get("gathered_message") else list()) + (
                    delta["tool_messages"] if delta.get("tool_messages") else list()
                )
        elif k == "structured":
            if not delta.get(k):
                formatted_delta[k] = dict()
            try:
                formatted_delta[k] = loads_json(delta.get(k))
            except (json.JSONDecodeError, TypeError):
                formatted_delta[k] = dict()
        else:
            # Default empty values for list fields
            default = {} if k in ("structured",) else [] if k in ("tool_calls", "tool_messages", "tool_results") else ""
            formatted_delta[k] = delta.get(k, default)
    return formatted_delta if (not reduce or len(formatted_delta) != 1) else next(iter(formatted_delta.values()))


def gather_assistant_message(message_chunks: List[Dict]):
    """\
    Gather assistant message_chunks (returned by `_LLMChunk.to_message()`) from a list of message dictionaries.

    Args:
        message_chunks (List[Dict]): A list of message dictionaries to gather.

    Returns:
        Dict[str, Any]: A dictionary containing the gathered assistant message.
    """
    gathered = {"role": "assistant", "content": "", "tool_calls": list()}
    for message_chunk in message_chunks:
        gathered["content"] += message_chunk.get("content", "")
        gathered["tool_calls"].extend(message_chunk.get("tool_calls", list()))
    if not gathered.get("tool_calls"):
        del gathered["tool_calls"]
    return gathered


LLMResponse = Union[str, Dict[str, Any], List[Union[str, Dict[str, Any]]]]


def gather_stream(stream: Iterable[Dict[str, Any]], include: Optional[List[LLMIncludeType]] = None, reduce: bool = True) -> LLMResponse:
    """\
    Gather an iterable of `LLM.stream` responses into a single consolidated `LLM.oracle` response.
    To use `gather_stream`, the stream must uses `reduce=False` to return a dictionary per delta.

    Args:
        stream (Iterable[LLMResponse]): An iterable of LLM responses from `LLM.stream`.
        include (List[LLMIncludeType] | None): Fields to include in the final output.
            If None, includes all fields found in the stream.
            This can usually be omitted if the stream was generated with the desired `include` fields.
            However, when the streaming fails (empty), this ensures the final output has the expected structure.
        reduce (bool): Whether to reduce the final output if only one field is included.

    Returns:
        LLMResponse: The consolidated LLM response.
    """
    response = dict()
    if include is not None:
        for key in include:
            if key in _LLM_TEXT_INCLUDES:
                response[key] = ""
            elif key in _LLM_LIST_INCLUDES:
                response[key] = list()
            elif key == "structured":
                response[key] = dict()
            elif key == "message":
                response[key] = {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": list(),
                }
            else:
                raise_mismatch(supported=_LLM_INCLUDES, got=key, name="include key for `gather_stream`", thres=1.0)
    for delta in stream:
        if delta is None:
            continue
        for key, value in delta.items():
            if (include is not None) and (key not in include):
                continue
            if key in _LLM_TEXT_INCLUDES:
                response[key] = response.get(key, "") + (value or "")
            elif key in _LLM_LIST_INCLUDES:
                response[key] = response.get(key, list()) + (value or list())
            elif key == "structured":
                response[key] = response.get(key, dict()) | (value or dict())
            elif key == "message":
                response[key] = response.setdefault(
                    key,
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": list(),
                    },
                )
                response[key]["content"] += value.get("content") or ""
                response[key]["tool_calls"].extend(value.get("tool_calls") or list())
    if ("message" in response) and ("tool_calls" in response["message"]) and (not response["message"].get("tool_calls")):
        del response["message"]["tool_calls"]
    response = response if (include is None) else {k: response.get(k) for k in unique(include)}
    return response if (not reduce or len(response) != 1) else next(iter(response.values()))


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
            retry=retry_if_exception_type(tuple(get_litellm_retryable_exceptions())),
            reraise=reraise,
        )

    def _cached_stream(self, **inputs) -> Generator[Any, None, None]:
        @self._get_retry()
        def vanilla_stream(**inputs) -> Generator[Any, None, None]:
            litellm = get_litellm()
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
            litellm = get_litellm()
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
            litellm = get_litellm()
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
            litellm = get_litellm()
            embeddings_resp = await litellm.aembedding(input=non_empty_batch, **kwargs)
            embeddings = embeddings_resp.data
            return [self.embed_empty if i in empty else embeddings.pop(0)["embedding"] for i in range(len(batch))]

        @self.cache.batch_memoize(name=self.name)
        async def cached_vanilla_aembed(batch: List[str], **kwargs) -> List[List[float]]:
            return await vanilla_aembed(batch, **kwargs)

        return await cached_vanilla_aembed(batch, **kwargs)

    def _validate_include(
        self,
        include: Optional[List[LLMIncludeType]] = None,
        stream: bool = True,
        has_tools: bool = False,
        has_structured: bool = False,
        toolspec_dict: Optional[Dict[str, Optional["ToolSpec"]]] = None,
    ) -> List[str]:
        """\
        Validate and normalize include fields.

        Args:
            include: Fields to include, or None for defaults.
            stream: Whether this is a streaming request.
            has_tools: Whether tools are provided.
            has_structured: Whether structured output is expected.
            toolspec_dict: Dict mapping tool names to ToolSpec (for tool_messages/tool_results validation).

        Returns:
            Validated and normalized list of include fields.
        """
        # Smart defaults based on whether tools are present
        if include is None:
            include = ["think", "text", "tool_calls"] if has_tools else ["text"]
        if isinstance(include, str):
            include = [include]
        if has_structured and ("structured" not in include):
            include.append("structured")
        include = unique(include)
        # if stream and ("messages" in include):
        #     raise ValueError("Return mode 'messages' is not supported for streaming requests, use `oracle` instead.")
        if not len(include):
            raise ValueError("Include list must not be empty.")
        for item in include:
            raise_mismatch(supported=_LLM_INCLUDES, got=item, name="include key", thres=1.0)
        # Validate tool_messages/tool_results: requires all tools to be ToolSpec
        needs_execution = ("tool_messages" in include) or ("tool_results" in include) or ("delta_messages" in include) or ("messages" in include)
        if needs_execution and toolspec_dict:
            for name, spec in toolspec_dict.items():
                if spec is None:
                    raise ValueError(
                        f"tool_messages/tool_results/messages/delta_messages requires all tools to be ToolSpec instances, "
                        f"but tool '{name}' is a raw jsonschema dict."
                    )
        # Validate structured output: requires `response_format` in config
        if ("structured" in include) and (not has_structured):
            raise ValueError("Including 'structured' output requires a 'response_format' to be specified in the LLM config.")
        return include

    def _validate_config(
        self,
        messages: Messages,
        tools: Optional[List[Union[Dict, "ToolSpec"]]] = None,
        tool_choice: Optional[str] = None,
        **kwargs,
    ) -> tuple:
        """\
        Validate and prepare config for LLM call.

        Args:
            messages: The messages to send.
            tools: Optional list of tools (ToolSpec or jsonschema dicts).
            tool_choice: Optional tool choice setting.
            **kwargs: Additional config overrides.

        Returns:
            tuple: (config_dict, toolspec_dict)
        """
        jsonschema_list, toolspec_dict = _normalize_tools(tools)

        config = deepcopy(self.config) | deepcopy(kwargs) | {"messages": messages} | {"stream": True}

        # Add tools to config if present
        if jsonschema_list:
            config["tools"] = jsonschema_list
            # Default tool_choice: "auto" if tools present and not specified
            if tool_choice is None:
                tool_choice = "auto"
            config["tool_choice"] = tool_choice
        elif tool_choice is not None:
            config["tool_choice"] = tool_choice

        return config, toolspec_dict

    def stream(
        self,
        messages: Messages,
        tools: Optional[List[Union[Dict, "ToolSpec"]]] = None,
        tool_choice: Optional[str] = None,
        include: Optional[List[LLMIncludeType]] = None,
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
        - Tool support: when tools are provided, tool_calls are aggregated and yielded at the end.
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
            tools: Optional list of tools, each can be a ToolSpec or jsonschema dict.
                When provided, include defaults to ["think", "text", "tool_calls"].
            tool_choice: Tool choice setting. Defaults to "auto" if tools present, otherwise None.
            include: Fields to include in each streamed delta. Can be a str or list[str].
                Allowed: "text", "think", "tool_calls", "content", "message", "structured", "tool_messages", "tool_results", "delta_messages", "messages".
                Default: ["text"] without tools, ["think", "text", "tool_calls"] with tools.
            verbose: If True, logs the resolved request config.
            reduce: If True and len(include) == 1, returns a single value instead of a dict.
                If False, always returns a dict.
            **kwargs: Per-call overrides for LLM config (e.g., temperature, top_p, http_proxy, https_proxy, etc.).

        Yields:
            LLMResponse:
                - dict if len(include) > 1 or reduce == False
                - single value if len(include) == 1 and reduce == True
                When tools are present, tool_calls/tool_messages/tool_results are yielded at the end after all text.

        Raises:
            ValueError: if `include` is empty or contains unsupported fields (e.g., "messages").
            ValueError: if `tool_messages` or `tool_results` is in include but some tools are not ToolSpec.
        """
        formatted_messages = format_messages(messages)
        config, toolspec_dict = self._validate_config(messages=formatted_messages, tools=tools, tool_choice=tool_choice, **kwargs)
        has_tools, has_structured = bool(tools), bool("response_format" in config)
        include = self._validate_include(include=include, stream=True, has_tools=has_tools, has_structured=has_structured, toolspec_dict=toolspec_dict)
        has_messages = bool(("delta_messages" in include) or ("messages" in include))

        repair_tool_calls = bool(config.pop("repair_tool_calls", True))
        with NetworkProxy(
            http_proxy=config.pop("http_proxy", None),
            https_proxy=config.pop("https_proxy", None),
        ):
            if verbose:
                logger.info(f"HTTP  Proxy: {os.environ.get('HTTP_PROXY')}")
                logger.info(f"HTTPS Proxy: {os.environ.get('HTTPS_PROXY')}")
                logger.info(f"Request: {encrypt_config(config)}")

            response = _LLMChunk()
            for chunk in self._cached_stream(**config):
                response += chunk[0]
                delta_dict = response.to_dict_delta()

                # When tools present, don't yield tool_calls incrementally
                if has_tools:
                    delta_dict["tool_calls"] = list()
                # When structured output is requested, don't yield partial output
                if has_structured:
                    delta_dict["structured"] = ""
                # When messages requested, use empty list to bypass messages deepcopy
                if has_messages:
                    delta_dict["messages"] = list()
                    delta_dict["delta_messages"] = list()

                if (not delta_dict.get("text")) and (not delta_dict.get("think")) and (not delta_dict.get("content")):
                    continue  # Skip empty deltas
                yield _llm_response_formatting(delta=delta_dict, include=include, messages=list(), reduce=reduce)

            # Yield final tool_calls/tool_messages/tool_results/structured/delta_messages/messages after stream ends
            if repair_tool_calls:
                tool_calls = [repair_tool_call(tool_call, toolspec_dict) for tool_call in response.tool_calls]
            else:
                tool_calls = response.tool_calls
            final_delta = {
                "think": "",
                "text": "",
                "tool_calls": tool_calls if tool_calls else list(),
                "content": "",
                "message": {"role": "assistant", "content": ""} | ({"tool_calls": tool_calls} if tool_calls else {}),
                "gathered_message": response.to_message(),
            }
            # Execute tools if tool_messages or tool_results requested
            if response.tool_calls and (("tool_messages" in include) or ("tool_results" in include) or has_messages):
                tool_messages, tool_results = exec_tool_calls(tool_calls, toolspec_dict)
                final_delta["tool_messages"] = tool_messages
                final_delta["tool_results"] = tool_results
            if has_structured:
                final_delta["structured"] = response.text
            if has_messages:
                final_delta["messages"] = None  # Explicitly set to None to trigger construction in formatting
                final_delta["delta_messages"] = None  # Explicitly set to None to trigger construction in formatting
            yield _llm_response_formatting(delta=final_delta, include=include, messages=formatted_messages, reduce=reduce)
            return

    async def astream(
        self,
        messages: Messages,
        tools: Optional[List[Union[Dict, "ToolSpec"]]] = None,
        tool_choice: Optional[str] = None,
        include: Optional[List[LLMIncludeType]] = None,
        verbose: bool = False,
        reduce: bool = True,
        **kwargs,
    ) -> AsyncGenerator[LLMResponse, None]:
        """\
        Asynchronously stream LLM responses (deltas) for the given messages.

        Mirrors :meth:`stream` but returns an async generator suitable for async workflows.

        Warning: `tools` are not yet supported in async mode and will raise NotImplementedError if provided.
        """
        if tools is not None:
            raise NotImplementedError("Asynchronous streaming with tools is not yet supported.")

        formatted_messages = format_messages(messages)
        config, toolspec_dict = self._validate_config(messages=formatted_messages, tools=tools, tool_choice=tool_choice, **kwargs)
        has_tools, has_structured = bool(tools), bool("response_format" in config)
        include = self._validate_include(include=include, stream=True, has_tools=has_tools, has_structured=has_structured, toolspec_dict=toolspec_dict)
        has_messages = bool(("delta_messages" in include) or ("messages" in include))

        repair_tool_calls = bool(config.pop("repair_tool_calls", True))
        with NetworkProxy(
            http_proxy=config.pop("http_proxy", None),
            https_proxy=config.pop("https_proxy", None),
        ):
            if verbose:
                logger.info(f"HTTP  Proxy: {os.environ.get('HTTP_PROXY')}")
                logger.info(f"HTTPS Proxy: {os.environ.get('HTTPS_PROXY')}")
                logger.info(f"Request: {encrypt_config(config)}")

            response = _LLMChunk()
            async for chunk in self._cached_astream(**config):
                response += chunk[0]
                delta_dict = response.to_dict_delta()

                # When tools present, don't yield tool_calls incrementally
                if has_tools:
                    delta_dict["tool_calls"] = list()
                # When structured output is requested, don't yield partial output
                if has_structured:
                    delta_dict["structured"] = ""
                # When messages requested, use empty list to bypass messages deepcopy
                if has_messages:
                    delta_dict["messages"] = list()
                    delta_dict["delta_messages"] = list()

                if (not delta_dict.get("text")) and (not delta_dict.get("think")) and (not delta_dict.get("content")):
                    continue  # Skip empty deltas
                yield _llm_response_formatting(delta=delta_dict, include=include, messages=list(), reduce=reduce)

            # Yield final tool_calls/tool_messages/tool_results/structured/delta_messages/messages after stream ends
            if repair_tool_calls:
                tool_calls = [repair_tool_call(tool_call, toolspec_dict) for tool_call in response.tool_calls]
            else:
                tool_calls = response.tool_calls
            final_delta = {
                "think": "",
                "text": "",
                "tool_calls": tool_calls if tool_calls else list(),
                "content": "",
                "message": {"role": "assistant", "content": ""} | ({"tool_calls": tool_calls} if tool_calls else {}),
                "gathered_message": response.to_message(),
            }
            # Execute tools if tool_messages or tool_results requested
            if response.tool_calls and (("tool_messages" in include) or ("tool_results" in include) or has_messages):
                tool_messages, tool_results = exec_tool_calls(tool_calls, toolspec_dict)
                final_delta["tool_messages"] = tool_messages
                final_delta["tool_results"] = tool_results
            if has_structured:
                final_delta["structured"] = response.text
            if has_messages:
                final_delta["messages"] = None  # Explicitly set to None to trigger construction in formatting
                final_delta["delta_messages"] = None  # Explicitly set to None to trigger construction in formatting
            yield _llm_response_formatting(delta=final_delta, include=include, messages=formatted_messages, reduce=reduce)
            return

    def oracle(
        self,
        messages: Messages,
        tools: Optional[List[Union[Dict, "ToolSpec"]]] = None,
        tool_choice: Optional[str] = None,
        include: Optional[List[LLMIncludeType]] = None,
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
        - Tool support: can include tools and tool_results in response.
        - Proxies: supports `http_proxy` and `https_proxy` in kwargs.
        - Flexible input: accepts multiple message formats and normalizes them.
        - Output shaping: control returned fields with `include` and flattening with `reduce`.

        Args:
            messages: Conversation content, normalized by ``format_messages``.
            tools: Optional list of tools, each can be a ToolSpec or jsonschema dict.
                When provided, include defaults to ["think", "text", "tool_calls"].
            tool_choice: Tool choice setting. Defaults to "auto" if tools present.
            include: Fields to include in the final result. Can be a str or list[str].
                Allowed: "text", "think", "tool_calls", "content", "message", "structured", "tool_messages", "tool_results", "delta_messages", "messages".
                Default: ["text"] without tools, ["think", "text", "tool_calls"] with tools.
            verbose: If True, logs the resolved request config.
            reduce: If True and len(include) == 1, returns a single value instead of a dict.
                If False, always returns a dict.
            **kwargs: Per-call overrides for LLM config.

        Returns:
            LLMResponse:
                - dict if len(include) > 1 or reduce == False
                - single value if len(include) == 1 and reduce == True

        Raises:
            ValueError: if `include` is empty or contains unsupported fields.
            ValueError: if `tool_messages` or `tool_results` is in include but some tools are not ToolSpec.
        """
        stream = list()
        for chunk in self.stream(
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            include=include,
            verbose=verbose,
            reduce=False,  # Must use reduce=False for agather_stream
            **kwargs,
        ):
            stream.append(chunk)
        return gather_stream(stream, include=include, reduce=reduce)

    async def aoracle(
        self,
        messages: Messages,
        tools: Optional[List[Union[Dict, "ToolSpec"]]] = None,
        tool_choice: Optional[str] = None,
        include: Optional[List[LLMIncludeType]] = None,
        verbose: bool = False,
        reduce: bool = True,
        **kwargs,
    ) -> LLMResponse:
        """\
        Asynchronously retrieve the final LLM response (aggregated from the async stream).

        Mirrors :meth:`oracle` and shares its configuration, caching, and reduction semantics.
        """
        stream = list()
        async for chunk in self.astream(
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            include=include,
            verbose=verbose,
            reduce=False,  # Must use reduce=False for agather_stream
            **kwargs,
        ):
            stream.append(chunk)
        return gather_stream(stream, include=include, reduce=reduce)

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

    def tooluse(
        self,
        messages: Messages,
        tools: List[Union[Dict, "ToolSpec"]],
        tool_choice: str = "required",
        include: Optional[Union[str, List[str]]] = None,
        verbose: bool = False,
        reduce: bool = True,
        **kwargs,
    ) -> List[Dict]:
        """\
        Execute tool calls with the LLM.

        This is a convenience method that forces the LLM to use tools and returns the
        executed tool messages. It sets tool_choice="required" and returns tool_messages by default.

        Args:
            messages: Conversation content.
            tools: List of tools (ToolSpec instances required for execution).
            tool_choice: Tool choice setting. Defaults to "required".
            include: Fields to include in the result. Defaults to ["tool_messages"].
            verbose: If True, logs the resolved request config.
            reduce: If True, simplifies the output when possible.
            **kwargs: Per-call overrides for LLM config.

        Returns:
            List[Dict]: List of tool result messages in OpenAI format:
                [{"role": "tool", "tool_call_id": ..., "name": ..., "content": ...}, ...]

        Raises:
            ValueError: if tools are not ToolSpec instances.

        Example:
            >>> tool_messages = llm.tooluse("Calculate fib(10)", tools=[fib_tool])
            >>> print(tool_messages)
            [{"role": "tool", "tool_call_id": "...", "name": "fib", "content": "55"}]
            >>> # For repeated tool use iteration:
            >>> messages.append({"role": "assistant", "tool_calls": ...})
            >>> messages.extend(tool_messages)
            >>> tool_messages = llm.tooluse(messages, tools=[fib_tool])
        """
        return self.oracle(
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            include=["tool_messages"] if include is None else include,
            verbose=verbose,
            reduce=reduce,
            **kwargs,
        )

    async def atooluse(
        self,
        messages: Messages,
        tools: List[Union[Dict, "ToolSpec"]],
        verbose: bool = False,
        **kwargs,
    ) -> List[Dict]:
        """\
        Asynchronously execute tool calls with the LLM.

        Mirrors :meth:`tooluse` but awaits async streaming.
        """
        return await self.aoracle(
            messages=messages,
            tools=tools,
            tool_choice="required",
            include=["tool_messages"],
            verbose=verbose,
            reduce=True,
            **kwargs,
        )

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
