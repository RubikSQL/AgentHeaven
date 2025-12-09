__all__ = [
    "parse_keys",
    "parse_md",
    "parse_fc",
]


from .debug_utils import raise_mismatch

import ast
import re
from typing import Literal, Optional, List


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
    - Fenced code blocks (e.g., ```python ... ```, ```sql ... ```), languages are optional and case-sensitive. Missing language defaults to "markdown".
    - Plain text between blocks

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
    blocks = list()
    pattern = re.compile(r"(<(\w+)>([\s\S]*?)<\/\2>)|(```(\w*)\n([\s\S]*?)\n```)")

    last_end = 0
    for match in pattern.finditer(response):
        start, end = match.span()
        if last_end < start:
            content = response[last_end:start].strip()
            if content:
                blocks.append({"key": "text", "value": content})
        if match.group(1):
            tag = match.group(2)
            content = match.group(3).strip()
            blocks.append(
                {
                    "key": tag,
                    "value": ((parse_md(content, recurse=recurse, mode="list") if content else list()) if recurse else content),
                }
            )
        elif match.group(4):
            lang = match.group(5) if match.group(5) else "markdown"
            content = match.group(6).strip()
            blocks.append({"key": lang, "value": content})
        last_end = end
    if last_end < len(response):
        content = response[last_end:].strip()
        if content:
            blocks.append({"key": "text", "value": content})

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


def parse_fc(call: str):
    """Parse a simple function call string into name and arguments.

    Supported syntax mirrors typical Python-style calls with keyword arguments. Examples:

    - ``"fibonacci(n=32)"`` -> ``{"name": "fibonacci", "arguments": {"n": 32}}``
    - ``"foo(bar='baz', qux=true, nada=None)"`` -> booleans and ``None``/``null`` are normalized.
    - Empty argument lists like ``"ping()"`` yield an empty ``arguments`` dict.

    Args:
        call: The function call string, e.g., ``"func(a=1, b='x')"``.

    Returns:
        dict: ``{"name": <function_name>, "arguments": {<key>: <parsed_value>, ...}}``

    Raises:
        ValueError: If the call string cannot be parsed or contains positional arguments.
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
        raise ValueError("Expected key=value pairs in function arguments")

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

    arguments = dict()
    for part in _split_args(arg_str):
        key, value = _split_kv(part)
        arguments[key] = _convert(value)

    return {"name": name, "arguments": arguments}
