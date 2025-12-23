__all__ = [
    "load_txt",
    "iter_txt",
    "save_txt",
    "append_txt",
    "loads_yaml",
    "dumps_yaml",
    "load_yaml",
    "dump_yaml",
    "save_yaml",
    "load_pkl",
    "dump_pkl",
    "save_pkl",
    "load_hex",
    "dump_hex",
    "save_hex",
    "load_b64",
    "dump_b64",
    "save_b64",
    "serialize_path",
    "deserialize_path",
    "serialize_func",
    "deserialize_func",
    "AhvnJsonEncoder",
    "AhvnJsonDecoder",
    "loads_json",
    "dumps_json",
    "load_json",
    "dump_json",
    "save_json",
    "escape_json",
    "loads_jsonl",
    "dumps_jsonl",
    "load_jsonl",
    "iter_jsonl",
    "dump_jsonl",
    "save_jsonl",
    "append_jsonl",
]

import binascii
import base64
import os
import re
from .log_utils import get_logger

logger = get_logger(__name__)
from .path_utils import *
from .debug_utils import FunctionDeserializationError
from .config_utils import HEAVEN_CM, hpj
from .file_utils import exists_file, exists_dir, enum_files, enum_dirs

_encoding = HEAVEN_CM.get("core.encoding", "utf-8")

from typing import Any, Dict, List, Optional, Literal, Generator, Callable, Union
import json
import pickle
import inspect
import datetime


def loads_yaml(s: str, **kwargs) -> Any:
    """
    Load a YAML string into a Python object.

    Args:
        s (str): The YAML string to load.
        **kwargs: Additional keyword arguments to pass to `yaml.safe_load`.

    Returns:
        Any: The loaded Python object.
    """
    import yaml

    return yaml.safe_load(s, **kwargs)


def load_txt(path: str, encoding: str = None, strict: bool = False) -> str:
    """\
    Load text from a file. If the file does not exist, returns an empty string.

    Args:
        path (str): The path to the file.
        encoding (str): The encoding to use for reading the file. Defaults to None, which will use the encoding in the config file ("core.encoding").
        strict (bool): If True, raises an error if the file does not exist. Otherwise, returns an empty string.

    Returns:
        str: The contents of the file or an empty string if the file does not exist.

    Raises:
        FileNotFoundError: If the file does not exist and `strict` is True.
    """
    path = hpj(path, abs=True)
    if not exists_file(path):
        if strict:
            raise FileNotFoundError(f"File {path} does not exist.")
        return ""
    with open(path, "r", encoding=encoding or _encoding, errors="ignore") as fp:
        return fp.read()


def iter_txt(path: str, encoding: str = None, strict: bool = False) -> Generator[str, None, None]:
    """\
    Iterate over a text file, yielding each line (stripping the newline character at the end).

    Args:
        path (str): The path to the file.
        encoding (str): The encoding to use for reading the file. Defaults to None, which will use the encoding in the config file ("core.encoding").
        strict (bool): If True, raises an error if the file does not exist. Otherwise, returns an empty generator.

    Yields:
        str: Each line in the text file.

    Raises:
        FileNotFoundError: If the file does not exist and `strict` is True.
    """
    path = hpj(path, abs=True)
    if not exists_file(path):
        if strict:
            raise FileNotFoundError(f"File {path} does not exist.")
        return
    with open(path, "r", encoding=encoding or _encoding, errors="ignore") as fp:
        for line in fp:
            yield line.rstrip("\n")
    return


def save_txt(obj: Any, path: str, encoding: str = None):
    """\
    Save text to a file. If the file does not exist, it will be created.

    Warning:
        An extra newline will be added at the end of the string to be consistent with the behavior of `append_txt`.

    Args:
        obj (Any): The text to save.
        path (str): The path to the file.
        encoding (str): The encoding to use for writing the file. Defaults to None, which will use the encoding in the config file ("core.encoding").
    """
    path = hpj(path, abs=True)
    dir = get_file_dir(path)
    if dir:
        os.makedirs(dir, exist_ok=True)
    with open(path, "w", encoding=encoding or _encoding, errors="ignore") as fp:
        fp.write(str(obj) + "\n")


def append_txt(obj: Any, path: str, encoding: str = None):
    """\
    Append text to a file. If the file does not exist, it will be created.

    Args:
        obj (Any): The text to append.
        path (str): The path to the file.
        encoding (str): The encoding to use for writing the file. Defaults to None, which will use the encoding in the config file ("core.encoding").
    """
    path = hpj(path, abs=True)
    dir = get_file_dir(path)
    if dir:
        os.makedirs(dir, exist_ok=True)
    with open(path, "a", encoding=encoding or _encoding, errors="ignore") as fp:
        fp.write(str(obj) + "\n")


def dumps_yaml(obj: Any, sort_keys: bool = False, indent: int = 4, allow_unicode: bool = True, **kwargs) -> str:
    """\
    Serialize a Python object to a YAML string.

    Args:
        obj (Any): The Python object to serialize.
        sort_keys (bool): Whether to sort the keys in the YAML output. Defaults to False.
        indent (int): The number of spaces to use for indentation. Defaults to 4.
        allow_unicode (bool): Whether to allow Unicode characters in the output. Defaults to True.
        **kwargs: Additional keyword arguments to pass to `yaml.safe_dump`.

    Returns:
        str: The YAML string representation of the object.
    """
    import yaml

    return yaml.safe_dump(obj, sort_keys=sort_keys, indent=indent, allow_unicode=allow_unicode, **kwargs)


def load_yaml(path: str, encoding: str = None, strict: bool = False, **kwargs) -> Any:
    """\
    Load a YAML file into a Python object.

    Args:
        path (str): The path to the YAML file.
        encoding (str): The encoding to use for reading the file. Defaults to None, which will use the encoding in the config file ("core.encoding").
        strict (bool): If True, raises an error if the file does not exist. Otherwise, returns an empty dictionary.
        **kwargs: Additional keyword arguments to pass to `yaml.safe_load`.

    Returns:
        Any: The Python object represented by the YAML file.

    Raises:
        FileNotFoundError: If the file does not exist and `strict` is True.
    """
    import yaml

    path = hpj(path, abs=True)
    if not exists_file(path):
        if strict:
            raise FileNotFoundError(f"File {path} does not exist.")
        return dict()
    with open(path, "r", encoding=encoding or _encoding, errors="ignore") as fp:
        return yaml.safe_load(fp, **kwargs)


def dump_yaml(
    obj: Any,
    path: str,
    sort_keys: bool = False,
    indent: int = 4,
    allow_unicode: bool = True,
    **kwargs,
):
    """\
    Save a Python object to a YAML file.

    Args:
        obj (Any): The Python object to save.
        path (str): The path to the YAML file.
        sort_keys (bool): Whether to sort the keys in the YAML output. Defaults to False.
        indent (int): The number of spaces to use for indentation. Defaults to 4.
        allow_unicode (bool): Whether to allow Unicode characters in the output. Defaults to True.
        **kwargs: Additional keyword arguments to pass to `yaml.safe_dump`.
    """
    import yaml

    path = hpj(path, abs=True)
    dir = get_file_dir(path)
    if dir:
        os.makedirs(dir, exist_ok=True)
    with open(path, "w", encoding=_encoding, errors="ignore") as fp:
        yaml.safe_dump(
            obj,
            fp,
            sort_keys=sort_keys,
            indent=indent,
            allow_unicode=allow_unicode,
            **kwargs,
        )


def save_yaml(
    obj: Any,
    path: str,
    sort_keys: bool = False,
    indent: int = 4,
    allow_unicode: bool = True,
    **kwargs,
):
    """\
    Alias for `dump_yaml`. Saves a Python object to a YAML file.

    Args:
        obj (Any): The Python object to save.
        path (str): The path to the YAML file.
        sort_keys (bool): Whether to sort the keys in the YAML output. Defaults to False.
        indent (int): The number of spaces to use for indentation. Defaults to 4.
        allow_unicode (bool): Whether to allow Unicode characters in the output. Defaults to True.
        **kwargs: Additional keyword arguments to pass to `yaml.safe_dump`.
    """
    import yaml

    path = hpj(path, abs=True)
    dir = get_file_dir(path)
    if dir:
        os.makedirs(dir, exist_ok=True)
    with open(path, "w", encoding=_encoding, errors="ignore") as fp:
        yaml.safe_dump(
            obj,
            fp,
            sort_keys=sort_keys,
            indent=indent,
            allow_unicode=allow_unicode,
            **kwargs,
        )


def load_pkl(path: str, strict: bool = False, **kwargs) -> Any:
    """\
    Load a Python object from a pickle file.

    Args:
        path (str): The path to the pickle file.
        strict (bool): If True, raises an error if the file does not exist. Otherwise, returns None.
        **kwargs: Additional keyword arguments to pass to `pickle.load`.

    Returns:
        Any: The Python object represented by the pickle file.
    """
    path = hpj(path, abs=True)
    if not exists_file(path):
        if strict:
            raise FileNotFoundError(f"File {path} does not exist.")
        return None
    with open(path, "rb") as fp:
        return pickle.load(fp, **kwargs)


def dump_pkl(obj: Any, path: str, **kwargs):
    """\
    Save a Python object to a pickle file.

    Args:
        obj (Any): The Python object to save.
        path (str): The path to the pickle file.
        **kwargs: Additional keyword arguments to pass to `pickle.dump`.
    """
    path = hpj(path, abs=True)
    dir = get_file_dir(path)
    if dir:
        os.makedirs(dir, exist_ok=True)
    with open(path, "wb") as fp:
        pickle.dump(obj, fp, **kwargs)


def save_pkl(obj: Any, path: str, **kwargs):
    """\
    Alias for `dump_pkl`. Saves a Python object to a pickle file.

    Args:
        obj (Any): The Python object to save.
        path (str): The path to the pickle file.
        **kwargs: Additional keyword arguments to pass to `pickle.dump`.
    """
    path = hpj(path, abs=True)
    dir = get_file_dir(path)
    if dir:
        os.makedirs(dir, exist_ok=True)
    with open(path, "wb") as fp:
        pickle.dump(obj, fp, **kwargs)


def load_hex(path: str, strict: bool = False, **kwargs) -> str:
    """\
    Load the binary contents of a file as a hexadecimal string.

    Args:
        path (str): The path to the file.
        strict (bool): If True, raises an error if the file does not exist. Otherwise, returns an empty string.
        **kwargs: Additional keyword arguments to pass to `bytes.hex`.

    Returns:
        str: The hexadecimal string representation of the file's contents.
    """
    path = hpj(path, abs=True)
    if not exists_file(path):
        if strict:
            raise FileNotFoundError(f"File {path} does not exist.")
        return ""
    with open(path, "rb") as fp:
        return binascii.hexlify(fp.read(), **kwargs).decode("utf-8")


def dump_hex(obj: str, path: str, **kwargs):
    """\
    Save a string or bytes object as a hexadecimal string to a file.

    Args:
        obj (str): The string or bytes object to save as hexadecimal.
        path (str): The path to the file.
        **kwargs: Additional keyword arguments to pass to `binascii.hexlify`.
    """
    path = hpj(path, abs=True)
    dir = get_file_dir(path)
    if dir:
        os.makedirs(dir, exist_ok=True)
    with open(path, "wb") as fp:
        fp.write(binascii.unhexlify(obj.encode("utf-8"), **kwargs))


def save_hex(obj: str, path: str, **kwargs):
    """\
    Alias for `dump_hex`. Saves a string or bytes object as a hexadecimal string to a file.

    Args:
        obj (str): The string or bytes object to save as hexadecimal.
        path (str): The path to the file.
        **kwargs: Additional keyword arguments to pass to `binascii.hexlify`.
    """
    path = hpj(path, abs=True)
    dir = get_file_dir(path)
    if dir:
        os.makedirs(dir, exist_ok=True)
    with open(path, "wb") as fp:
        fp.write(binascii.unhexlify(obj.encode("utf-8"), **kwargs))


def load_b64(path: str, strict: bool = False) -> str:
    """\
    Load the binary contents of a file as a Base64-encoded string.

    Args:
        path (str): The path to the file.
        strict (bool): If True, raises an error if the file does not exist. Otherwise, returns an empty string.

    Returns:
        str: The Base64 string representation of the file's contents.
    """
    path = hpj(path, abs=True)
    if not exists_file(path):
        if strict:
            raise FileNotFoundError(f"File {path} does not exist.")
        return ""
    with open(path, "rb") as fp:
        return base64.b64encode(fp.read()).decode("utf-8")


def dump_b64(obj: str, path: str):
    """\
    Save a Base64 string to a file by decoding it into binary content.

    Args:
        obj (str): The Base64 string to decode and save.
        path (str): The path to the output file.
    """
    path = hpj(path, abs=True)
    dir = get_file_dir(path)
    if dir:
        os.makedirs(dir, exist_ok=True)
    with open(path, "wb") as fp:
        fp.write(base64.b64decode(obj.encode("utf-8")))


def save_b64(obj: str, path: str):
    """\
    Alias for `dump_b64`. Saves a Base64 string to a file by decoding it into binary content.

    Args:
        obj (str): The Base64 string to decode and save.
        path (str): The path to the output file.
    """
    path = hpj(path, abs=True)
    dir = get_file_dir(path)
    if dir:
        os.makedirs(dir, exist_ok=True)
    with open(path, "wb") as fp:
        fp.write(base64.b64decode(obj.encode("utf-8")))


def serialize_path(path: str) -> Dict[str, Optional[str]]:
    """\
    Serialize the contents of a directory hierarchy into a dictionary mapping relative paths to Base64-encoded file contents.

    Directories are recorded with a value of ``None`` so the structure can be rehydrated later.

    Args:
        path (str): Directory (or file) path to serialize.

    Returns:
        Dict[str, Optional[str]]: Mapping of relative paths to Base64 payloads (or ``None`` for directories).
    """
    path_abs = hpj(path, abs=True)
    if not (exists_dir(path_abs) or exists_file(path_abs)):
        raise FileNotFoundError(f"Path {path_abs} does not exist.")

    serialized: Dict[str, Optional[str]] = dict()

    if exists_file(path_abs):
        serialized[get_file_basename(path_abs)] = load_b64(path_abs)
        return serialized

    for rel_dir in enum_dirs(path_abs, abs=False):
        serialized[rel_dir] = None

    for rel_file in enum_files(path_abs, abs=False):
        serialized[rel_file] = load_b64(hpj(path_abs, rel_file, abs=True))

    return serialized


def deserialize_path(serialized: Dict[str, Optional[str]], path: str):
    """\
    Materialize files and directories described by ``serialized`` under ``path``.

    Args:
        serialized (Dict[str, Optional[str]]): Mapping emitted by :func:`serialize_path`.
        path (str): Destination directory where content should be written.
    """
    dest_root = hpj(path, abs=True)
    os.makedirs(dest_root, exist_ok=True)

    for rel_dir in sorted((p for p, content in serialized.items() if content is None), key=len):
        os.makedirs(os.path.join(dest_root, rel_dir), exist_ok=True)

    for rel_path, content in serialized.items():
        if content is None:
            continue
        target_path = os.path.join(dest_root, rel_path)
        dump_b64(content, target_path)


# TODO: `dill` is unsafe for function storage, as it stores the absolute path to the function's source code, which could result in unexpected behavior if the source code is moved, modified, or transferred to another physical location.


def _patched_getsource(func: Callable) -> str:
    if hasattr(func, "__source__"):
        return func.__source__
    import dill

    return dill.source.getsource(func)


def serialize_func(func: Callable, **kwargs) -> Dict:
    """\
    Serialize a function to a descriptor dictionary using `dill` for source code and `cloudpickle` for binary content.

    Args:
        func (Callable): The function to serialize.
        **kwargs: Additional keyword arguments to pass to `cloudpickle.dumps`.

    Returns:
        Dict: A dictionary representation of the serialized function. It contains the following attributes:
            Built-in Attributes:
            - name: The function's name.
            - qualname: The qualified name of the function.
            - doc: The function's docstring.
            - module: The qualified name of the module where the function is defined.
            - defaults: Default values for the function's positional arguments.
            - kwdefaults: Default values for the function's keyword-only arguments.
            - annotations: Type annotations for the function's arguments and return value.
            - code: The source code of the function (as a string, via `dill`).
            - dict: The function's `__dict__` (excluding `__source__`), with all values stringified.
            Extra Attributes:
            - stream: Whether the function is a generator function (bool).
            - hex_dumps: The function serialized as a hex string using `cloudpickle`.
    """
    import cloudpickle

    return {
        "name": func.__name__,
        "qualname": func.__qualname__,
        "doc": inspect.getdoc(func),
        "module": getattr(inspect.getmodule(func), "__qualname__", None),
        "defaults": getattr(func, "__defaults__", None),
        "kwdefaults": getattr(func, "__kwdefaults__", None),
        "annotations": {k: str(v) for k, v in getattr(func, "__annotations__", dict()).items()},
        "code": _patched_getsource(func),
        "dict": {k: str(v) for k, v in getattr(func, "__dict__", dict()).items() if k != "__source__"},
        "stream": bool(inspect.isgeneratorfunction(func)),
        "hex_dumps": cloudpickle.dumps(func, **kwargs).hex(),
    }


def _deserialize_from_source(code, name):
    namespace = dict()
    try:
        exec(code, namespace)
    except Exception as e:
        logger.error(f"Failed to exec code for function '{name}': {e}")
        raise FunctionDeserializationError(f"Failed to exec code: {e}")
    f = namespace.get(name, None)
    if f is None:
        logger.error(f"Function '{name}' not found after exec.")
        raise FunctionDeserializationError(f"Function '{name}' not found after exec.")
    return f


def _deserialize_from_hex(hexstr):
    try:
        import cloudpickle

        return cloudpickle.loads(bytes.fromhex(hexstr))
    except Exception as e:
        logger.error(f"Failed to load cloudpickle function from hex: {e}")
        raise FunctionDeserializationError(f"Failed to load cloudpickle function from hex: {e}")


def deserialize_func(func: Dict, prefer: Literal["code", "hex_dumps"] = "hex_dumps") -> Callable:
    """\
    Deserialize a function from a descriptor dictionary.

    Args:
        func (Dict): The function descriptor dictionary.
        prefer (Literal['code','hex_dumps']): Which method to try first.

    Returns:
        Callable: The deserialized function.

    Raises:
        FunctionDeserializationError: If deserialization fails.
    """
    # For lambda functions, prefer cloudpickle (hex_dumps) since source code extraction is problematic
    if (func.get("name") == "<lambda>") and (prefer != "hex_dumps"):
        logger.warning("Deserializing a lambda function; enforcing 'hex_dumps' method.")
        prefer = "hex_dumps"

    order = ["code", "hex_dumps"] if prefer == "code" else ["hex_dumps", "code"]
    exceptions = []

    for o in order:
        if o == "code" and func.get("code") and func.get("name"):
            try:
                return _deserialize_from_source(code=func.get("code"), name=func.get("name"))
            except Exception as e:
                logger.warning(f"Deserialization from source code failed: {e}")
                exceptions.append(e)
        elif o == "hex_dumps" and func.get("hex_dumps"):
            try:
                return _deserialize_from_hex(hexstr=func.get("hex_dumps"))
            except Exception as e:
                logger.warning(f"Deserialization from hex_dumps failed: {e}")
                exceptions.append(e)
    logger.error("Function deserialization failed with all available methods.")
    exceptions_str = "\n".join(str(e) for e in exceptions)
    raise FunctionDeserializationError(f"Deserialization failed:\n{exceptions_str}")


class AhvnJsonEncoder(json.JSONEncoder):
    def encode(self, obj):
        return super().encode(AhvnJsonEncoder.transform(obj))

    @staticmethod
    def transform(obj):
        if callable(obj):
            return {
                "__obj_type__": "function",
                "__obj_data__": serialize_func(obj),
            }
        if isinstance(obj, tuple):
            return {
                "__obj_type__": "tuple",
                "__obj_data__": [AhvnJsonEncoder.transform(item) for item in obj],
            }
        if isinstance(obj, set):
            return {
                "__obj_type__": "set",
                "__obj_data__": [AhvnJsonEncoder.transform(item) for item in sorted(list(obj))],
            }
        if isinstance(obj, datetime.datetime):
            return {
                "__obj_type__": "datetime",
                "__obj_data__": obj.timestamp(),
            }
        if isinstance(obj, int) and (obj > 1 << 53 or obj < -(1 << 53)):
            return {"__obj_type__": "bigint", "__obj_data__": str(obj)}
        if isinstance(obj, list):
            return [AhvnJsonEncoder.transform(item) for item in obj]
        if isinstance(obj, dict):
            return {k: AhvnJsonEncoder.transform(v) for k, v in obj.items()}
        if obj is Ellipsis:
            return {"__obj_type__": "ellipsis"}
        return obj


class AhvnJsonDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(object_hook=AhvnJsonDecoder.transform, *args, **kwargs)

    @staticmethod
    def transform(obj):
        if isinstance(obj, list):
            return [AhvnJsonDecoder.transform(item) for item in obj]
        if not isinstance(obj, dict):
            return obj
        if "__obj_type__" not in obj:
            return {k: AhvnJsonDecoder.transform(v) for k, v in obj.items()}
        if obj["__obj_type__"] == "function":
            try:
                return deserialize_func(obj["__obj_data__"])
            except FunctionDeserializationError as e:
                logger.error(f"Failed to deserialize function: {e}")
                return None
        if obj["__obj_type__"] == "tuple":
            return tuple(AhvnJsonDecoder.transform(item) for item in obj["__obj_data__"])
        if obj["__obj_type__"] == "set":
            return set(AhvnJsonDecoder.transform(item) for item in obj["__obj_data__"])
        if obj["__obj_type__"] == "datetime":
            return datetime.datetime.fromtimestamp(obj["__obj_data__"])
        if obj["__obj_type__"] == "bigint":
            return int(obj["__obj_data__"])
        if obj["__obj_type__"] == "ellipsis":
            return ...
        return obj


def loads_json(s: str, **kwargs) -> Any:
    """\
    Load a JSON string into a Python object.

    Args:
        s (str): The JSON string to load.
        **kwargs: Additional keyword arguments to pass to `json.loads`.

    Returns:
        Any: The Python object represented by the JSON string.
    """
    return json.loads(s, cls=AhvnJsonDecoder, **kwargs)


def dumps_json(obj: Any, sort_keys: bool = False, indent: int = 4, ensure_ascii: bool = False, **kwargs) -> str:
    """\
    Serialize a Python object to a JSON string.

    Args:
        obj (Any): The Python object to serialize.
        sort_keys (bool): Whether to sort the keys in the JSON output. Defaults to False.
        indent (int): The number of spaces to use for indentation. Defaults to 4.
        ensure_ascii (bool): Whether to escape non-ASCII characters. Defaults to False.
        **kwargs: Additional keyword arguments to pass to `json.dumps`.

    Returns:
        str: The JSON string representation of the object.
    """
    return json.dumps(obj, cls=AhvnJsonEncoder, sort_keys=sort_keys, indent=indent, ensure_ascii=ensure_ascii, **kwargs)


def load_json(path: str, encoding: str = None, strict: bool = False, **kwargs) -> Any:
    """\
    Load a JSON file into a Python object.

    Args:
        path (str): The path to the JSON file.
        encoding (str): The encoding to use for reading the file. Defaults to None, which will use the encoding in the config file ("core.encoding").
        strict (bool): If True, raises an error if the file does not exist. Otherwise, returns an empty dictionary.
        **kwargs: Additional keyword arguments to pass to `json.load`.

    Returns:
        Any: The Python object represented by the JSON file.

    Raises:
        FileNotFoundError: If the file does not exist and `strict` is True.
    """
    path = hpj(path, abs=True)
    if not exists_file(path):
        if strict:
            raise FileNotFoundError(f"File {path} does not exist.")
        return dict()
    with open(path, "r", encoding=encoding or _encoding, errors="ignore") as fp:
        return json.load(fp, cls=AhvnJsonDecoder, **kwargs)


def dump_json(
    obj: Any,
    path: str,
    sort_keys: bool = False,
    indent: int = 4,
    encoding: str = None,
    ensure_ascii: bool = False,
    **kwargs,
):
    """\
    Save a Python object to a JSON file.

    Args:
        obj (Any): The Python object to save.
        path (str): The path to the JSON file.
        sort_keys (bool): Whether to sort the keys in the JSON output. Defaults to False.
        indent (int): The number of spaces to use for indentation. Defaults to 4.
        encoding (str): The encoding to use for writing the file. Defaults to None, which will use the encoding in the config file ("core.encoding").
        ensure_ascii (bool): Whether to escape non-ASCII characters. Defaults to False.
        **kwargs: Additional keyword arguments to pass to `json.dump`.
    """
    path = hpj(path, abs=True)
    dir = get_file_dir(path)
    if dir:
        os.makedirs(dir, exist_ok=True)
    with open(path, "w", encoding=encoding or _encoding, errors="ignore") as fp:
        json.dump(obj, fp, cls=AhvnJsonEncoder, sort_keys=sort_keys, indent=indent, ensure_ascii=ensure_ascii, **kwargs)


def save_json(
    obj: Any,
    path: str,
    sort_keys: bool = False,
    indent: int = 4,
    encoding: str = None,
    ensure_ascii: bool = False,
    **kwargs,
):
    """\
    Alias for `dump_json`. Saves a Python object to a JSON file.

    Args:
        obj (Any): The Python object to save.
        path (str): The path to the JSON file.
        sort_keys (bool): Whether to sort the keys in the JSON output. Defaults to False.
        indent (int): The number of spaces to use for indentation. Defaults to 4.
        encoding (str): The encoding to use for writing the file. Defaults to None, which will use the encoding in the config file ("core.encoding").
        ensure_ascii (bool): Whether to escape non-ASCII characters. Defaults to False.
        **kwargs: Additional keyword arguments to pass to `json.dump`.
    """
    path = hpj(path, abs=True)
    dir = get_file_dir(path)
    if dir:
        os.makedirs(dir, exist_ok=True)
    with open(path, "w", encoding=encoding or _encoding, errors="ignore") as fp:
        json.dump(obj, fp, cls=AhvnJsonEncoder, sort_keys=sort_keys, indent=indent, ensure_ascii=ensure_ascii, **kwargs)


def escape_json(s: str, args: List[str], **kwargs) -> str:
    """
    Fixes corrupted JSON by escaping string values for known keys.

    - Only processes keys listed in `args`
    - Only escapes string values
    - Leaves non-string values untouched
    - Handles unescaped quotes and newlines inside strings

    Args:
        s (str): The corrupted JSON string.
        args (List[str]): List of keys whose string values need to be escaped.
        **kwargs: Additional keyword arguments to pass to `json.dumps` when returning the repaired JSON

    Returns:
        str: The repaired JSON string.
    """

    try:
        return dumps_json(loads_json(s), **kwargs)
    except json.JSONDecodeError:
        pass

    # Strip trailing whitespace/newlines
    s = s.strip()

    result = {}
    i = 0
    n = len(s)

    def skip_whitespace():
        nonlocal i
        while i < n and s[i] in " \t\n\r":
            i += 1

    def parse_string_key():
        """Parse a properly quoted key string."""
        nonlocal i
        if s[i] != '"':
            raise ValueError(f"Expected '\"' at position {i}")
        i += 1
        start = i
        while i < n and s[i] != '"':
            if s[i] == "\\" and i + 1 < n:
                i += 2
            else:
                i += 1
        if i >= n:
            raise ValueError("Unterminated string key")
        key = s[start:i]
        i += 1
        return key

    def find_value_end_for_key(key: str):
        """Find end of value for a known key - handles corrupted string values."""
        nonlocal i
        skip_whitespace()
        if i >= n:
            return None

        # Non-string values: arrays, objects, numbers, booleans, null
        if s[i] == "[":
            # Array - find matching bracket
            depth = 1
            i += 1
            in_str = False
            while i < n and depth > 0:
                if s[i] == '"' and (i == 0 or s[i - 1] != "\\"):
                    in_str = not in_str
                elif not in_str:
                    if s[i] == "[":
                        depth += 1
                    elif s[i] == "]":
                        depth -= 1
                i += 1
            try:
                return json.loads(s[start_pos:i])
            except json.JSONDecodeError:
                # Try to parse as list of strings
                arr_content = s[start_pos + 1 : i - 1].strip()
                items = []
                for item in arr_content.split(","):
                    item = item.strip()
                    if item.startswith('"') and item.endswith('"'):
                        items.append(item[1:-1])
                    elif item:
                        try:
                            items.append(json.loads(item))
                        except json.JSONDecodeError:
                            items.append(item)
                return items
        elif s[i] == "{":
            # Nested object - find matching brace
            depth = 1
            i += 1
            in_str = False
            while i < n and depth > 0:
                if s[i] == '"' and (i == 0 or s[i - 1] != "\\"):
                    in_str = not in_str
                elif not in_str:
                    if s[i] == "{":
                        depth += 1
                    elif s[i] == "}":
                        depth -= 1
                i += 1
            return json.loads(s[start_pos:i])
        elif s[i] == '"':
            # String value - this is where corruption may occur
            i += 1  # skip opening quote

            # Find the next key pattern or end of object to determine where value ends
            next_key_patterns = []
            for arg in args:
                next_key_patterns.append(f'"{arg}"')
                next_key_patterns.append(f', "{arg}"')

            # Look for end: either ", "key": or "}
            value_chars = []
            while i < n:
                # Check if we're at end of object
                if s[i] == "}" and (not value_chars or value_chars[-1] != "\\"):
                    # Check if previous char was closing quote
                    if value_chars and value_chars[-1] == '"':
                        value_chars.pop()
                        break
                    # Otherwise include everything up to here
                    break

                # Check for pattern: ", "key":
                found_next_key = False
                for arg in args:
                    pattern1 = f', "{arg}":'
                    pattern2 = f',"{arg}":'
                    if s[i:].startswith(pattern1) or s[i:].startswith(pattern2):
                        # End of current value - remove trailing quote if present
                        if value_chars and value_chars[-1] == '"':
                            value_chars.pop()
                        found_next_key = True
                        break
                if found_next_key:
                    break

                value_chars.append(s[i])
                i += 1

            value = "".join(value_chars)
            return value
        else:
            # Number, boolean, null
            start = i
            while i < n and s[i] not in ",}]\n\r":
                i += 1
            token = s[start:i].strip()
            if token == "true":
                return True
            elif token == "false":
                return False
            elif token == "null":
                return None
            else:
                try:
                    if "." in token:
                        return float(token)
                    return int(token)
                except ValueError:
                    return token

    # Parse the JSON object
    skip_whitespace()
    if s[i] != "{":
        raise ValueError(f"Expected '{{' at position {i}")
    i += 1

    while i < n:
        skip_whitespace()
        if i >= n or s[i] == "}":
            break

        # Skip comma
        if s[i] == ",":
            i += 1
            skip_whitespace()

        if i >= n or s[i] == "}":
            break

        # Parse key
        key = parse_string_key()

        skip_whitespace()
        if s[i] != ":":
            raise ValueError(f"Expected ':' after key at position {i}")
        i += 1
        skip_whitespace()

        start_pos = i
        value = find_value_end_for_key(key)
        result[key] = value

    try:
        return dumps_json(result, **kwargs)
    except json.JSONDecodeError:
        raise ValueError(f"Failed to repair JSON string.\n{repr(s)}")


def loads_jsonl(s: str, **kwargs) -> List[Any]:
    """\
    Load a JSON Lines string into a list of Python objects.

    Args:
        s (str): The JSON Lines string to load.
        **kwargs: Additional keyword arguments to pass to `json.loads`.

    Returns:
        List[Any]: A list of Python objects represented by the JSON Lines string.
    """
    return [json.loads(line, cls=AhvnJsonDecoder, **kwargs) for line in s.splitlines() if line.strip()]


def dumps_jsonl(obj: List[Any], sort_keys: bool = False, ensure_ascii: bool = False, **kwargs) -> str:
    """\
    Serialize a list of Python objects to a JSON Lines string.

    Warning:
        An extra newline will be added at the end of the string to be consistent with the behavior of `append_jsonl`.
        `indent` is NOT a valid argument for this function, as JSON Lines does not support indentation. Passing `indent` will be ignored.

    Args:
        obj (List[Any]): The list of Python objects to serialize.
        sort_keys (bool): Whether to sort the keys in the JSON output. Defaults to False.
        ensure_ascii (bool): Whether to escape non-ASCII characters. Defaults to False.
        **kwargs: Additional keyword arguments to pass to `json.dumps`.

    Returns:
        str: The JSON Lines string representation of the list.
    """
    kwargs = {k: v for k, v in kwargs.items() if k != "indent"}
    return "\n".join(json.dumps(item, cls=AhvnJsonEncoder, sort_keys=sort_keys, indent=None, ensure_ascii=ensure_ascii, **kwargs) for item in obj) + "\n"


def load_jsonl(path: str, encoding: str = None, strict: bool = False, **kwargs) -> List[Any]:
    """\
    Load a JSON Lines file into a list of Python objects.

    Args:
        path (str): The path to the JSON Lines file.
        encoding (str): The encoding to use for reading the file. Defaults to None, which will use the encoding in the config file ("core.encoding").
        strict (bool): If True, raises an error if the file does not exist. Otherwise, returns an empty list.
        **kwargs: Additional keyword arguments to pass to `json.load`.

    Returns:
        List[Any]: A list of Python objects represented by the JSON Lines file.

    Raises:
        FileNotFoundError: If the file does not exist and `strict` is True.
    """
    path = hpj(path, abs=True)
    if not exists_file(path):
        if strict:
            raise FileNotFoundError(f"File {path} does not exist.")
        return list()
    with open(path, "r", encoding=encoding or _encoding, errors="ignore") as fp:
        return [json.loads(line, cls=AhvnJsonDecoder, **kwargs) for line in fp if line.strip()]


def iter_jsonl(path: str, encoding: str = None, strict: bool = False, **kwargs) -> Generator[Any, None, None]:
    """\
    Iterate over a JSON Lines file, yielding each Python object.

    Args:
        path (str): The path to the JSON Lines file.
        encoding (str): The encoding to use for reading the file. Defaults to None, which will use the encoding in the config file ("core.encoding").
        strict (bool): If True, raises an error if the file does not exist. Otherwise, returns an empty list.
        **kwargs: Additional keyword arguments to pass to `json.load`.

    Yields:
        Any: Each Python object represented by a line in the JSON Lines file.

    Raises:
        FileNotFoundError: If the file does not exist and `strict` is True.
    """
    path = hpj(path, abs=True)
    if not exists_file(path):
        if strict:
            raise FileNotFoundError(f"File {path} does not exist.")
        return
    with open(path, "r", encoding=encoding or _encoding, errors="ignore") as fp:
        for line in fp:
            if line.strip():
                yield json.loads(line, cls=AhvnJsonDecoder, **kwargs)
    return


def dump_jsonl(obj: List[Any], path: str, sort_keys: bool = False, ensure_ascii: bool = False, encoding: str = None, **kwargs):
    """\
    Save a list of Python objects to a JSON Lines file.

    Warning:
        An extra newline will be added at the end of the file to be consistent with the behavior of `append_jsonl`.
        `indent` is NOT a valid argument for this function, as JSON Lines does not support indentation. Passing `indent` will be ignored.

    Args:
        obj (List[Any]): The list of Python objects to save.
        path (str): The path to the JSON Lines file.
        sort_keys (bool): Whether to sort the keys in the JSON output. Defaults to False.
        ensure_ascii (bool): Whether to escape non-ASCII characters. Defaults to False.
        encoding (str): The encoding to use for writing the file. Defaults to None, which will use the encoding in the config file ("core.encoding").
        **kwargs: Additional keyword arguments to pass to `json.dump`.
    """
    path = hpj(path, abs=True)
    dir = get_file_dir(path)
    if dir:
        os.makedirs(dir, exist_ok=True)
    kwargs = {k: v for k, v in kwargs.items() if k != "indent"}
    with open(path, "w", encoding=encoding or _encoding, errors="ignore") as fp:
        fp.write("\n".join(json.dumps(o, cls=AhvnJsonEncoder, sort_keys=sort_keys, indent=None, ensure_ascii=ensure_ascii, **kwargs) for o in obj) + "\n")


def save_jsonl(obj: List[Any], path: str, sort_keys: bool = False, ensure_ascii: bool = False, encoding: str = None, **kwargs):
    """\
    Alias for `dump_jsonl`. Saves a list of Python objects to a JSON Lines file.

    Warning:
        An extra newline will be added at the end of the file to be consistent with the behavior of `append_jsonl`.
        `indent` is NOT a valid argument for this function, as JSON Lines does not support indentation. Passing `indent` will be ignored.

    Args:
        obj (List[Any]): The list of Python objects to save.
        path (str): The path to the JSON Lines file.
        sort_keys (bool): Whether to sort the keys in the JSON output. Defaults to False.
        ensure_ascii (bool): Whether to escape non-ASCII characters. Defaults to False.
        encoding (str): The encoding to use for writing the file. Defaults to None, which will use the encoding in the config file ("core.encoding").
        **kwargs: Additional keyword arguments to pass to `json.dump`.
    """
    path = hpj(path, abs=True)
    dir = get_file_dir(path)
    if dir:
        os.makedirs(dir, exist_ok=True)
    kwargs = {k: v for k, v in kwargs.items() if k != "indent"}
    with open(path, "w", encoding=encoding or _encoding, errors="ignore") as fp:
        fp.write("\n".join(json.dumps(o, cls=AhvnJsonEncoder, sort_keys=sort_keys, indent=None, ensure_ascii=ensure_ascii, **kwargs) for o in obj) + "\n")


def append_jsonl(
    obj: Union[Dict, List[Any]],
    path: str,
    sort_keys: bool = False,
    ensure_ascii: bool = False,
    encoding: str = None,
    **kwargs,
):
    """\
    Append a list of Python objects to a JSON Lines file. If the file does not exist, it will be created. If the object is a dictionary, a single line will be added with the dictionary serialized as JSON. If the object is a list, each item in the list will be serialized as a separate line in the JSON Lines file.

    Args:
        obj (Union[Dict,List[Any]]): The list of Python objects to append.
        path (str): The path to the JSON Lines file.
        sort_keys (bool): Whether to sort the keys in the JSON output. Defaults to False.
        ensure_ascii (bool): Whether to escape non-ASCII characters. Defaults to False.
        encoding (str): The encoding to use for writing the file. Defaults to None, which will use the encoding in the config file ("core.encoding").
        **kwargs: Additional keyword arguments to pass to `json.dump`.
    """
    path = hpj(path, abs=True)
    dir = get_file_dir(path)
    if dir:
        os.makedirs(dir, exist_ok=True)
    kwargs = {k: v for k, v in kwargs.items() if k != "indent"}
    with open(path, "a", encoding=encoding or _encoding, errors="ignore") as fp:
        if isinstance(obj, dict):
            fp.write(json.dumps(obj, cls=AhvnJsonEncoder, sort_keys=sort_keys, indent=None, ensure_ascii=ensure_ascii, **kwargs) + "\n")
        elif isinstance(obj, list):
            fp.write("\n".join(json.dumps(o, cls=AhvnJsonEncoder, sort_keys=sort_keys, indent=None, ensure_ascii=ensure_ascii, **kwargs) for o in obj) + "\n")
