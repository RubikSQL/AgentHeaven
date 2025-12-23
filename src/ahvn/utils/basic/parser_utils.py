__all__ = [
    "parse_keys",
    "parse_md",
    "parse_fc",
]


from .debug_utils import raise_mismatch

import ast
import re
from typing import Literal, Optional, List, Dict


def parse_keys(response: str, keys: Optional[List[str]] = None, mode: Literal["list", "dict"] = "dict"):
    """\
    Parse keys from an LLM response based on the provided mode.
    The LLM response is expected to be formatted as "<key>: <value>" pairs.

    Args:
        response (str): The LLM response containing key-value pairs.
        keys (list, optional): A list of keys to parse from the response. If None, all keys will be parsed.
        mode (Literal['list', 'dict'], optional): The mode of parsing. 'list' returns a list of key-value pairs, while 'dict' returns a dictionary with keys and their corresponding values.

    Returns:
        list or dict: Parsed key-value pairs in the specified mode.

    Examples:
        >>> parse_keys("name: John Doe\\nage: 30", keys=["name", "age", "height"], mode="list")
        [{'key': 'name', 'value': 'John Doe'}, {'key': 'age', 'value': '30'}]
        >>> parse_keys("name: John Doe\\nage: 30", keys=["name", "age", "height"], mode="dict")
        {'name': 'John Doe', 'age': '30', 'height': None}
    """
    key_occurs = list()
    if keys is None:
        for match in re.finditer(r"^(\w+):", response, re.MULTILINE):
            key_occurs.append({"key": match.group(1), "start": match.start(), "end": match.end()})
    else:
        keys = list(keys)
        for key in keys:
            for match in re.finditer(re.escape(key) + r":", response):
                key_occurs.append({"key": key, "start": match.start(), "end": match.end()})
    sorted_key_occurs = sorted(key_occurs, key=lambda x: x["start"])
    blocks = list()
    for i, key_occurrence in enumerate(sorted_key_occurs):
        end = key_occurrence["end"]
        next_start = sorted_key_occurs[i + 1]["start"] if i + 1 < len(sorted_key_occurs) else len(response)
        value = response[end:next_start].strip()
        blocks.append({"key": key_occurrence["key"], "value": value})
    if mode == "list":
        return blocks
    elif mode == "dict":
        parsed = {key: None for key in ([block["key"] for block in blocks] if keys is None else keys)}
        for block in blocks:
            parsed[block["key"]] = block["value"]
        return parsed
    raise_mismatch(["list", "dict"], got=mode, name="mode")


def parse_md(response: str, recurse: bool = False, mode: Literal["list", "dict"] = "dict"):
    """\
    Parses a markdown-like string into structured blocks.

    This function extracts blocks from the input string that are either:

    - XML-like tags (e.g., <tag>...</tag>)
    - Fenced code blocks (e.g., ```python ... ```, ````sql ... ````), languages are optional and case-sensitive.
      Supports variable-length backtick fences (3+ backticks). Missing language defaults to "markdown".
    - Plain text between blocks

    This parser is streaming-compatible: incomplete/unfinished input will never raise errors and will produce
    the best possible parse result given the available data.

    Args:
        response (str): The input string to parse.

        recurse (bool, optional): If True, recursively parses nested blocks. Defaults to False.

        mode (Literal["list", "dict"], optional):

            - "list": Returns a list of blocks, each as a dict with 'key' and 'value'.
            - "dict": Returns a flattened dictionary with dot-separated keys for nested blocks. Notice that duplicate keys will be overwritten.

            Defaults to "dict".

    Returns:
        Union[list[dict], dict]: The parsed structure, as a list or dict depending on ``mode``.

    Examples:
        >>> parse_md("<think>Hello!</think>\\nSome textual output.\\n```sql\\nSELECT *\\nFROM table;\\n```\\n<rating>\\n```json\\n{\\\"rating\\\": 5}\\n```</rating>")
        {'think': 'Hello!', 'text': 'Some textual output.', 'sql': 'SELECT *\\nFROM table;', 'rating': '```json\\n{"rating": 5}\\n```'}

        >>> parse_md("<think>Hello!</think>\\nSome textual output.\\n```sql\\nSELECT *\\nFROM table;\\n```\\n<rating>\\n```json\\n{\\\"rating\\\": 5}\\n```</rating>", recurse=True)
        {'think.text': 'Hello!', 'text': 'Some textual output.', 'sql': 'SELECT *\\nFROM table;', 'rating.json': '{"rating": 5}'}

        >>> parse_md("<think>Hello!</think>\\nSome textual output.\\n```sql\\nSELECT *\\nFROM table;\\n```\\n<rating>\\n```json\\n{\\\"rating\\\": 5}\\n```</rating>", mode="list")
        [{'key': 'think', 'value': 'Hello!'}, {'key': 'text', 'value': 'Some textual output.'}, {'key': 'sql', 'value': 'SELECT *\\nFROM table;'}, {'key': 'rating', 'value': '```json\\n{"rating": 5}\\n```'}]
    """
    blocks = _parse_md_blocks(response, recurse=recurse)

    if mode == "list":
        return blocks
    elif mode == "dict":
        parsed = dict()

        def _dfs(blocks, prefix=None):
            prefix = prefix or list()
            for block in blocks:
                if isinstance(block["value"], list):
                    _dfs(block["value"], prefix=prefix + [block["key"]])
                else:
                    parsed[".".join(prefix + [block["key"]])] = block["value"]

        _dfs(blocks)
        return parsed
    raise_mismatch(["list", "dict"], got=mode, name="mode")


def _parse_md_blocks(response: str, recurse: bool = False) -> List[Dict]:
    """Internal function to parse markdown blocks with streaming support."""
    blocks = list()
    i = 0
    n = len(response)
    text_buffer = list()

    def flush_text():
        nonlocal text_buffer
        if text_buffer:
            content = "".join(text_buffer).strip()
            if content:
                blocks.append({"key": "text", "value": content})
            text_buffer = list()

    while i < n:
        # Check for XML-like tag opening: <tag>
        if response[i] == "<" and i + 1 < n and response[i + 1].isalpha():
            tag_match = re.match(r"<(\w+)>", response[i:])
            if tag_match:
                tag = tag_match.group(1)
                tag_open_end = i + len(tag_match.group(0))

                # Find matching closing tag </tag>
                close_pos = _find_matching_close_tag(response, tag, tag_open_end)

                if close_pos != -1:
                    # Found matching close tag
                    flush_text()
                    content = response[tag_open_end:close_pos].strip()
                    if recurse and content:
                        nested = _parse_md_blocks(content, recurse=True)
                        blocks.append({"key": tag, "value": nested if nested else list()})
                    else:
                        blocks.append({"key": tag, "value": content})
                    i = close_pos + len(tag) + 3  # len("</tag>") = len(tag) + 3
                    continue
                else:
                    # No matching close tag found (streaming case) - treat rest as content inside tag
                    flush_text()
                    content = response[tag_open_end:].strip()
                    if recurse and content:
                        nested = _parse_md_blocks(content, recurse=True)
                        blocks.append({"key": tag, "value": nested if nested else list()})
                    else:
                        blocks.append({"key": tag, "value": content})
                    i = n
                    continue

        # Check for fenced code block with 3+ backticks
        if response[i] == "`":
            backtick_count = 0
            j = i
            while j < n and response[j] == "`":
                backtick_count += 1
                j += 1

            if backtick_count >= 3:
                # Parse the language identifier (optional, until newline)
                lang_start = j
                while j < n and response[j] != "\n":
                    j += 1
                lang = response[lang_start:j].strip() if lang_start < j else ""
                if not lang:
                    lang = "markdown"

                # Find the closing fence (same number of backticks)
                fence = "`" * backtick_count
                code_start = j + 1 if j < n else j
                close_pos = _find_code_fence_close(response, fence, code_start)

                if close_pos != -1:
                    # Found closing fence
                    flush_text()
                    content = response[code_start:close_pos].strip()
                    blocks.append({"key": lang, "value": content})
                    i = close_pos + len(fence)
                    # Skip trailing newline if present
                    if i < n and response[i] == "\n":
                        i += 1
                    continue
                else:
                    # No closing fence found (streaming case) - treat rest as code content
                    flush_text()
                    content = response[code_start:].strip()
                    blocks.append({"key": lang, "value": content})
                    i = n
                    continue

        # Regular character - add to text buffer
        text_buffer.append(response[i])
        i += 1

    flush_text()
    return blocks


def _find_matching_close_tag(response: str, tag: str, start: int) -> int:
    """Find the matching closing tag, handling nested tags of the same name."""
    open_tag_pattern = re.compile(rf"<{re.escape(tag)}>")
    close_tag_pattern = re.compile(rf"</{re.escape(tag)}>")

    depth = 1
    i = start
    n = len(response)

    while i < n and depth > 0:
        # Look for next open or close tag
        open_match = open_tag_pattern.search(response, i)
        close_match = close_tag_pattern.search(response, i)

        if close_match is None:
            # No closing tag found
            return -1

        if open_match is None or close_match.start() < open_match.start():
            # Closing tag comes first
            depth -= 1
            if depth == 0:
                return close_match.start()
            i = close_match.end()
        else:
            # Opening tag comes first
            depth += 1
            i = open_match.end()

    return -1


def _find_code_fence_close(response: str, fence: str, start: int) -> int:
    """Find the closing code fence, must be at the start of a line."""
    i = start
    n = len(response)

    while i < n:
        # Look for the fence pattern
        pos = response.find(fence, i)
        if pos == -1:
            return -1

        # Check if fence is at start of line (or preceded by newline)
        if pos == 0 or response[pos - 1] == "\n":
            # Verify it's the exact fence (not more backticks)
            fence_len = len(fence)
            end_pos = pos + fence_len
            if end_pos >= n or response[end_pos] != "`":
                return pos

        i = pos + 1

    return -1


def _resolve_positional_args(tool_args: List[str], positional_args: List, keyword_args: Dict):
    final_args = dict()
    positional_args = positional_args.copy()
    for idx, param in enumerate(tool_args):
        if param in keyword_args:
            final_args[param] = keyword_args[param]
            continue
        if not len(positional_args):
            raise ValueError("Not enough positional arguments provided.")
        final_args[param] = positional_args.pop(0)
    return final_args


def parse_fc(call: str, tools_args: Optional[Dict] = None):
    """Parse a simple function call string into name, positional and keyword arguments.

    Supported syntax mirrors typical Python-style calls with both positional and keyword arguments. Examples:

    - ``"fibonacci(32)"`` -> ``{"name": "fibonacci", "positional_args": [32], "keyword_args": {}}``
    - ``"fibonacci(n=32)"`` -> ``{"name": "fibonacci", "positional_args": [], "keyword_args": {"n": 32}}``
    - ``"foo(1, 'baz', qux=true, nada=None)"`` -> booleans and ``None``/``null`` are normalized.
    - ``"foo(1, bar='baz', 2)"`` -> mixed positional and keyword arguments.
    - Empty argument lists like ``"ping()"`` yield empty positional and keyword arg collections.

    Args:
        call: The function call string, e.g., ``"func(1, a='x')"``.
        tools_args: Optional dictionary mapping function names to their argument names (list of strings). This is used to resolve positional arguments into keyword arguments when both are present.

    Returns:
        dict: ``{"name": <function_name>, "positional_args": [val1, ...], "keyword_args": {<key>: <parsed_value>, ...}}``

    Raises:
        ValueError: If the call string cannot be parsed.
    """

    def _split_args(arg_str: str):
        parts = list()
        current = list()
        depth = 0
        in_single = False
        in_double = False

        for ch in arg_str:
            if ch == "'" and not in_double:
                in_single = not in_single
            elif ch == '"' and not in_single:
                in_double = not in_double
            elif ch in "([{" and not in_single and not in_double:
                depth += 1
            elif ch in ")]}" and not in_single and not in_double and depth > 0:
                depth -= 1
            if ch == "," and depth == 0 and not in_single and not in_double:
                part = "".join(current).strip()
                if part:
                    parts.append(part)
                current = list()
                continue
            current.append(ch)
        tail = "".join(current).strip()
        if tail:
            parts.append(tail)
        return parts

    def _split_kv(item: str):
        depth = 0
        in_single = False
        in_double = False
        for idx, ch in enumerate(item):
            if ch == "'" and not in_double:
                in_single = not in_single
            elif ch == '"' and not in_single:
                in_double = not in_double
            elif ch in "([{" and not in_single and not in_double:
                depth += 1
            elif ch in ")]}" and not in_single and not in_double and depth > 0:
                depth -= 1
            if ch == "=" and depth == 0 and not in_single and not in_double:
                return item[:idx].strip(), item[idx + 1 :].strip()
        return None, item

    def _convert(value: str):
        lowered = value.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        if lowered in {"none", "null"}:
            return None
        try:
            return ast.literal_eval(value)
        except Exception:
            return value

    match = re.match(r"^\s*([A-Za-z_]\w*)\s*(?:\((.*)\))?\s*$", call)
    if not match:
        raise ValueError("Invalid function call format")

    name = match.group(1)
    arg_str = match.group(2)
    if arg_str is None or not arg_str.strip():
        return {"name": name, "arguments": dict()}

    positional_args = list()
    keyword_args = dict()

    for part in _split_args(arg_str):
        key, value = _split_kv(part)
        if key is not None:
            keyword_args[key] = _convert(value)
        else:
            positional_args.append(_convert(value))

    if positional_args:
        if (tools_args is None) or (name not in tools_args):
            raise ValueError(f"Positional arguments parsing requires tool definitions for function '{name}', which is not provided.")
        keyword_args = _resolve_positional_args(tools_args.get(name), positional_args, keyword_args)

    return {"name": name, "arguments": keyword_args}
