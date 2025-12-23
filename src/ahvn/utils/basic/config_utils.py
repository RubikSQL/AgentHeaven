__all__ = [
    "dmerge",
    "dget",
    "dset",
    "dunset",
    "dsetdef",
    "dflat",
    "dunflat",
    "ConfigManager",
    "HEAVEN_CM",
    "hpj",
    "encrypt_config",
]

from .log_utils import get_logger

logger = get_logger(__name__)
from .misc_utils import lflat
from .debug_utils import raise_mismatch
from .path_utils import pj, get_file_dir

from typing import Any, Dict, List, Optional, Literal, Generator, Iterable
from copy import deepcopy

__rnd_sep = "#@#@#"


def _split_key_path(key_path: str) -> List[str]:
    """\
    Split a key path string into a list of keys, handling escaped dots.
    """
    return [key.replace(__rnd_sep, ".") for key in key_path.replace("\\.", __rnd_sep).split(".") if key]


def dmerge(iterable: Iterable[Dict[str, Any]], start: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """\
    Merge multiple dictionaries into a single dictionary, with later dictionaries overwriting earlier ones. Nested dictionaries are merged recursively while all other non-dictionary values are overwritten.

    Warning:
        The merging of dictionaries is not order-preserving. The order of keys in the resulting dictionary may not match the order of keys in the input dictionaries.

    Args:
        iterable (Iterable[Dict[str, Any]]): An iterable of dictionaries to merge.
        start (Optional[Dict[str, Any]]): An optional starting dictionary to merge into.

    Returns:
        Dict[str, Any]: The merged dictionary.

    Examples:
        >>> d1 = {'a': 1, 'b': {'c': 2, 'f': 5}}
        >>> d2 = {'b': {'d': 3, 'f': 0}, 'e': 4}
        >>> dmerge([d1, d2])
        {'a': 1, 'b': {'c': 2, 'f': 0, 'd': 3}, 'e': 4}
        >>> dmerge([d2, d1])
        {'b': {'d': 3, 'f': 5, 'c': 2}, 'e': 4, 'a': 1}
        >>> dmerge([d1, d2], start={'a': 0, 'g': 6})
        {'a': 1, 'g': 6, 'b': {'c': 2, 'f': 0, 'd': 3}, 'e': 4}
    """
    if start is None:
        start = dict()
    else:
        start = deepcopy(start)
    for d in iterable:
        if not d:
            continue
        if "_OVERWRITE_" in d and d["_OVERWRITE_"]:
            start = deepcopy({k: v for k, v in d.items() if k != "_OVERWRITE_"})
            continue
        for k, v in d.items():
            if (k in start) and isinstance(v, dict):
                start[k] = dmerge([v], start=start[k])
            else:
                start[k] = v
    return start


def dget(d: Dict[str, Any], key_path: Optional[str] = None, default: Optional[Any] = None) -> Any:
    """\
    Get a value from a dictionary using a dot-separated key path. If the key path does not exist, return the default value.

    Args:
        d (Dict[str, Any]): The dictionary to search.
        key_path (Optional[str]): The dot-separated key path to the value.
        default (Optional[Any]): The default value to return if the key path does not exist.

    Returns:
        Any: The value at the specified key path or the default value if not found.

    Examples:
        >>> dget({'a': {'b': {'c': 42}}}, 'a.b.c')
        42
        >>> dget({'a': {'b': {'c': 42}}}, 'a.b.d', default='not found')
        'not found'
        >>> dget({'a': {'b': {'c': [1, 2, 3]}}}, 'a.b.c[1]')
        2
    """
    if key_path is None:
        return d
    keys = _split_key_path(key_path)
    for key in keys:
        if d is None:
            return default
        if key.endswith("]"):
            k, idx = key[:-1].rsplit("[", 1)
            idx = int(idx)
            if (k not in d) or (not isinstance(d[k], list)) or (idx >= len(d[k])) or (idx < -len(d[k])):
                return default
            d = d[k][idx]
        elif key not in d:
            return default
        else:
            d = d[key]
    return d


def dset(d: Dict[str, Any], key_path: str, value: Optional[Any] = None) -> bool:
    """\
    Set a value in a dictionary using a dot-separated key path. If the key path does not exist, it will be created.

    Args:
        d (Dict[str, Any]): The dictionary to modify.
        key_path (str): The dot-separated key path to the value.
        value (Optional[Any]): The value to set at the specified key path.

    Returns:
        bool: True if the value was set successfully, False if the key path is invalid.

    Examples:
        >>> d = {}
        >>> dset(d, 'a.b.c', 42)
        True
        >>> d
        {'a': {'b': {'c': 42}}}
    """
    if key_path is None:
        if not isinstance(value, dict):
            return False
        d.update(value)
        return True
    keys = _split_key_path(key_path)
    for key in keys[:-1]:
        if key.endswith("]"):
            k, idx = key[:-1].rsplit("[", 1)
            idx = int(idx)
            if (k not in d) or (not isinstance(d[k], list)) or (idx >= len(d[k])) or (idx < -len(d[k])):
                return False
            d = d[k][idx]
        elif key not in d:
            d[key] = dict()
            d = d[key]
        else:
            d = d[key]
    last_key = keys[-1]
    if last_key.endswith("]"):
        k, idx = last_key[:-1].rsplit("[", 1)
        idx = int(idx)
        if k not in d:
            d[k] = list()
        if (not isinstance(d[k], list)) or (idx < -len(d[k])):
            return False
        if idx >= len(d[k]):
            d[k].extend([None] * (idx - len(d[k]) + 1))
        d[k][idx] = value
    else:
        d[last_key] = value
    return True


def dunset(d: Dict[str, Any], key_path: str) -> bool:
    """\
    Unset a value in a dictionary using a dot-separated key path. If the key path does not exist, it will be ignored.

    Args:
        d (Dict[str, Any]): The dictionary to modify.
        key_path (str): The dot-separated key path to the value to unset.

    Returns:
        bool: True if the value was unset successfully, False if the key path is invalid.

    Examples:
        >>> d = {'a': {'b': {'c': 42}}}
        >>> dunset(d, 'a.b.c')
        True
        >>> d
        {'a': {'b': {}}}
    """
    if key_path is None:
        d.clear()
        return True
    keys = _split_key_path(key_path)
    for key in keys[:-1]:
        if key.endswith("]"):
            k, idx = key[:-1].rsplit("[", 1)
            idx = int(idx)
            if (k not in d) or (not isinstance(d[k], list)) or (idx >= len(d[k])) or (idx < -len(d[k])):
                return False
            d = d[k][idx]
        elif key not in d:
            return False
        else:
            d = d[key]
    last_key = keys[-1]
    if last_key.endswith("]"):
        k, idx = last_key[:-1].rsplit("[", 1)
        idx = int(idx)
        if (k not in d) or (not isinstance(d[k], list)) or (idx >= len(d[k])) or (idx < -len(d[k])):
            return False
        if idx < 0:
            idx += len(d[k])
        del d[k][idx]
    else:
        if last_key in d:
            del d[last_key]
        else:
            return False
    return True


def dsetdef(d: Dict[str, Any], key_path: str, default: Optional[Any] = None) -> bool:
    """\
    Set a default value in a dictionary using a dot-separated key path if the key path does not exist.

    Notice that if key_path exists but its value is None, the default value will also be set.

    Args:
        d (Dict[str, Any]): The dictionary to modify.
        key_path (str): The dot-separated key path to the value.
        default (Optional[Any]): The default value to set at the specified key path if it does not exist.

    Returns:
        bool: True if the default value was set successfully, False if the key path is invalid or already exists.

    Examples:
        >>> d = {}
        >>> dsetdef(d, 'a.b.c', 42)
        True
        >>> d
        {'a': {'b': {'c': 42}}}
        >>> dsetdef(d, 'a.b.c', 100)
        False
        >>> d
        {'a': {'b': {'c': 42}}}
    """
    if dget(d, key_path, default=None) is not None:
        return False
    return dset(d, key_path, default)


def dflat(d: Dict[str, Any], prefix: str = "", enum: bool = False) -> Generator[str, None, None]:
    """\
    Flatten a nested dictionary into a flat dictionary with dot-separated keys.

    Args:
        d (Dict[str, Any]): The dictionary to flatten.
        prefix (str): The prefix to prepend to the keys. Defaults to an empty string.
        enum (bool): If True, apart from leaf nodes, also include intermediate nodes in the flattened output. Defaults to False.

    Yields:
        Generator[str, None, None]: A generator yielding key-value pairs in the flattened format.

    Examples:
        >>> dict(dflat({'a': {'b': {'c': 42, 'd': [1, 2, 3]}}, 'e': 5}))
        {'a.b.c': 42, 'a.b.d[0]': 1, 'a.b.d[1]': 2, 'a.b.d[2]': 3, 'e': 5}
        >>> dict(dflat({'a': {'b': {'c': 42, 'd': [1, 2, 3]}}, 'e': 5}, enum=True))
        {'a': {'b': {'c': 42, 'd': [1, 2, 3]}}, 'a.b': {'c': 42, 'd': [1, 2, 3]}, 'a.b.c': 42, 'a.b.d': [1, 2, 3], 'a.b.d[0]': 1, 'a.b.d[1]': 2, 'a.b.d[2]': 3, 'e': 5}
    """

    def _dlist(d: Dict[str, Any], prefix: str = "", enum: bool = False) -> Generator[str, None, None]:
        for k, v in d.items():
            ck = k.replace(".", "\\.")
            if enum:
                yield ((".".join([prefix, ck]) if prefix else ck), v)
            if isinstance(v, dict):
                yield from _dlist(v, prefix=".".join([prefix, ck]) if prefix else ck, enum=enum)
            elif isinstance(v, list):
                for i, item in enumerate(v):
                    yield from _dlist({f"{ck}[{i}]": item}, prefix=prefix, enum=enum)
            elif not enum:
                yield ((".".join([prefix, ck]) if prefix else ck), v)

    yield from _dlist(d, prefix=prefix, enum=enum)


def dunflat(d: Dict[str, Any]) -> Dict[str, Any]:
    """\
    Unflatten a flat dictionary with dot-separated keys into a nested dictionary.

    Args:
        d (Dict[str, Any]): The flat dictionary to unflatten.

    Returns:
        Dict[str, Any]: The nested dictionary.

    Examples:
        >>> d = {'a.b.c': 42}
        >>> dunflat(d)
        {'a': {'b': {'c': 42}}}
    """
    merged = dict()
    for k, v in d.items():
        dset(merged, k, v)
    return merged


# Copy functions from file_utils.py to avoid circular imports
import os
import shutil


def _touch_dir(path: str, clear: bool = False) -> str:
    path = os.path.abspath(path)
    if clear and os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)
    return path


def _exists_file(path: str) -> bool:
    path = os.path.abspath(path)
    return os.path.exists(path) and os.path.isfile(path)


def _exists_dir(path: str) -> bool:
    path = os.path.abspath(path)
    return os.path.exists(path) and os.path.isdir(path)


# Copy functions from serialize_utils.py to avoid circular imports


def _load_yaml(path: str) -> Dict[str, Any]:
    import yaml

    path = os.path.abspath(path)
    if not _exists_file(path):
        return dict()
    with open(path, "r", encoding="utf-8", errors="ignore") as fp:
        return yaml.safe_load(fp)


def _save_yaml(obj: Any, path: str, sort_keys: bool = False, indent: int = 4):
    import yaml

    path = os.path.abspath(path)
    if os.path.dirname(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", errors="ignore") as fp:
        yaml.safe_dump(obj, fp, sort_keys=sort_keys, indent=indent, allow_unicode=True)


class ConfigManager:
    name: str = "ahvn"
    package: str = "ahvn"

    def __init__(self, name: Optional[str] = None, package: Optional[str] = None, cwd: Optional[str] = None):
        super().__init__()
        self._config: Optional[Dict[str, Any]] = None
        self._system_config: Optional[Dict[str, Any]] = None
        self._global_config: Optional[Dict[str, Any]] = None
        self._local_config: Optional[Dict[str, Any]] = None
        self.name = name or self.__class__.name
        self.package = package or self.__class__.package
        self.root = pj("~", f".{self.name}", abs=True)
        self.set_cwd(cwd)

    def set_cwd(self, cwd: Optional[str] = None):
        """\
        Set the current working directory for the configuration manager.

        Args:
            cwd (str): The new current working directory.
        """
        self.cwd = pj(cwd or os.getcwd(), abs=True)
        self.local = self._find_local()
        if self.local == self.root:
            logger.warning(
                f"Local configuration directory is the same as the root directory: {self.local}. This may cause issues with configuration management. ConfigManager will not load the configuration. Use `set_cwd` to set a different working directory. Otherwise using this class may lead to unexpected errors."
            )
        else:
            self._config = None
            self._system_config = None
            self._global_config = None
            self._local_config = None

    def _find_local(self) -> str:
        """\
        Find the local configuration directory from `self.cwd`, according to the GitHub repository finding rules.
        That is, it will look for the `.<name>` directory in the current working directory or its parents until reaching the root user directory (`~`). If the `.<name>` directory is found, it will be returned. If not found, it will return `<self.cwd>/.<name>`.

        Returns:
            str: The path to the local configuration directory.
        """
        path = pj(self.cwd, abs=True)
        while True:
            config_candidate = pj(path, f".{self.name}", abs=True)
            if config_candidate == self.root:
                break
            if _exists_dir(config_candidate):
                return config_candidate
            parent_path = get_file_dir(path)
            if parent_path == path:
                break
            path = parent_path
        return pj(self.cwd, f".{self.name}", abs=True)

    @property
    def local_dir(self) -> str:
        """\
        Get the local configuration directory.

        Returns:
            str: The path to the local configuration directory.
        """
        return get_file_dir(self.local, abs=True)

    @property
    def local_config_path(self) -> str:
        """\
        Get the path to the local configuration file.

        Returns:
            str: The path to the local configuration file.
        """
        return pj(self.local, "config.yaml", abs=True)

    @property
    def global_config_path(self) -> str:
        """\
        Get the path to the global configuration file.

        Returns:
            str: The path to the global configuration file.
        """
        return pj(self.root, "config.yaml", abs=True)

    @property
    def system_config_path(self) -> str:
        """\
        Get the path to the system configuration file.

        Returns:
            str: The path to the system configuration file.
        """
        return self.resource("configs", "default_config.yaml")

    def config_path(self, level: Literal[None, "local", "global", "system"] = None) -> str:
        """\
        Get the path to the configuration file for a specific level.

        Args:
            level (Literal[None, 'local', 'global', 'system']): The configuration level to get the path for. If None, returns the local configuration path.

        Returns:
            str: The path to the configuration file for the specified level.
        """
        if level is None or level == "local":
            return self.local_config_path
        if level == "global":
            return self.global_config_path
        if level == "system":
            return self.system_config_path
        raise_mismatch(["local", "global", "system", None], got=level, name="config level")

    def resource(self, *args: List[str]) -> str:
        """\
        Get the path to a resource file in the package `resources` directory.

        Args:
            *args (List[str]): The path components to the resource file.

        Returns:
            str: The absolute path to the resource file.
        """
        import importlib.resources

        with importlib.resources.as_file(importlib.resources.files(self.package).joinpath("resources", *args)) as path:
            return pj(str(path.resolve()), abs=True)

    @property
    def config(self) -> Dict[str, Any]:
        if self._config is None:
            self._config = dmerge([self.global_config, self.local_config])
        return self._config

    @property
    def system_config(self) -> Dict[str, Any]:
        if self._system_config is None:
            self._system_config = _load_yaml(self.system_config_path)
        return self._system_config

    @property
    def global_config(self) -> Dict[str, Any]:
        if self._global_config is None:
            self._global_config = _load_yaml(self.global_config_path)
        return self._global_config

    @property
    def local_config(self) -> Dict[str, Any]:
        if self._local_config is None:
            self._local_config = _load_yaml(self.local_config_path)
        return self._local_config

    def load(self):
        self._system_config = _load_yaml(self.system_config_path)
        self._global_config = _load_yaml(self.global_config_path)
        self._local_config = _load_yaml(self.local_config_path)
        self._config = dmerge([self.global_config, self.local_config])

    def save(self, level: Literal[None, "local", "global"] = None):
        if level in [None, "global"]:
            _save_yaml(self.global_config, self.global_config_path)
        if level in [None, "local"]:
            _save_yaml(self.local_config, self.local_config_path)
        self.load()

    def init(self, reset: bool = False) -> bool:
        """\
        Initialize the local configuration manager by loading the default configuration and creating the necessary directories.

        Args:
            reset (bool): If True, reset the local configuration to the default values.
        """
        if (not reset) and _exists_dir(self.local) and _exists_file(self.local_config_path):
            logger.info(f"Local configuration already exists at {self.local_config_path}. Use `reset=True` to overwrite it.")
            self.load()
            return False
        _touch_dir(self.local, clear=False)
        _save_yaml(dict(), self.local_config_path)
        self.load()
        return True

    def setup(self, reset: bool = False) -> bool:
        """\
        Setup the global configuration manager by initializing it and loading the configuration and creating the necessary directories.

        Args:
            reset (bool): If True, reset the global configuration to the default values.
        """
        if (not reset) and _exists_dir(self.root) and _exists_file(self.global_config_path):
            logger.info(f"Global configuration already exists at {self.global_config_path}. Use `reset=True` to overwrite it.")
            self.load()
            return False
        _touch_dir(self.root, clear=False)
        _save_yaml(self.system_config, self.global_config_path)
        self.load()
        return True

    def get(
        self,
        key_path: str = None,
        default: Optional[Any] = None,
        level: Literal[None, "local", "global", "system"] = None,
    ) -> Any:
        """\
        Get a value from the configuration using a dot-separated key path.

        Args:
            key_path (str): The dot-separated key path to the value.
            default (Any): The default value to return if the key path does not exist.
            level (Literal[None,'local','global']): The configuration level to use. If None, uses local configuration.

        Returns:
            Any: The value at the specified key path or the default value if not found.
        """
        if level is None:
            return dget(self.config, key_path, default=default)
        if level == "local":
            return dget(self.local_config, key_path, default=default)
        if level == "global":
            return dget(self.global_config, key_path, default=default)
        if level == "system":
            return dget(self.system_config, key_path, default=default)
        raise_mismatch(["local", "global", "system", None], got=level, name="config level to perform 'get' operation on")

    def set(self, key_path: str, value: Optional[Any] = None, level: Literal["local", "global"] = None) -> bool:
        """\
        Set a value in the configuration using a dot-separated key path.

        Args:
            key_path (str): The dot-separated key path to the value.
            value (Any): The value to set at the specified key path.
            level (Literal['local','global']): The configuration level to use. If None, uses local configuration.

        Returns:
            bool: True if the value was set successfully, False if the key path is invalid.
        """
        if level == "local":
            changed = dset(self.local_config, key_path, value)
            if changed:
                self.save(level="local")
            return changed
        if level == "global":
            changed = dset(self.global_config, key_path, value)
            if changed:
                self.save(level="global")
            return changed
        raise_mismatch(["local", "global"], got=level, name="config level to perform 'set' operation on")

    def unset(self, key_path: str, level: Literal["local", "global"] = None) -> bool:
        """\
        Unset a value in the configuration using a dot-separated key path.

        Args:
            key_path (str): The dot-separated key path to the value to unset.
            level (Literal['local','global']): The configuration level to use. If None, uses local configuration.

        Returns:
            bool: True if the value was unset successfully, False if the key path is invalid.
        """
        if level == "local":
            changed = dunset(self.local_config, key_path)
            if changed:
                self.save(level="local")
            return changed
        if level == "global":
            changed = dunset(self.global_config, key_path)
            if changed:
                self.save(level="global")
            return changed
        raise_mismatch(["local", "global"], got=level, name="config level to perform 'unset' operation on")


HEAVEN_CM = ConfigManager(name="ahvn", package="ahvn")


import re


def hpj(*args: List[str], abs: bool = False, cm: Optional[ConfigManager] = None) -> str:
    """\
    Join a list of strings into a path. Platform-agnostic. Spaces and trailing slashes are stripped from each argument.
    The following characters will be expanded:
    - '~' to the user's home directory.
    - '&' the `resources` directory of AgentHeaven. It is only recommended to use it at the beginning of the path.
    - '>' the local root folder (without `.ahvn/`) of the current AgentHeaven repository. It is only recommended to use it at the beginning of the path.

    Args:
        *args: Components of the path to join. Each argument should be a string.
        abs (bool, optional): If True, returns the absolute path. Defaults to False.
        cm (Optional[ConfigManager]): The configuration manager to use for resource and local directory resolution. Defaults to `HEAVEN_CM`.

    Returns:
        str: The joined, normalized path. Expands '~' to the user's home directory.

    Examples:
        >>> hpj("A", "B/C", " D/ ")
        'A/B/C/D'
        >>> hpj("A", "B/C", " D/ ", abs=True)
        '<path_to_cwd>/A/B/C'
        >>> hpj("~", "A", "B/C", " D/ ", abs=True)
        '<path_to_user_dir>/A/B/C'
        >>> hpj("&", "B", "C")
        '<path_to_ahvn>/resources/B/C'
        >>> hpj("& B", "C")
        '<path_to_ahvn>/resources/B/C'
        >>> hpj("&/B", "C")
        '<path_to_ahvn>/resources/B/C'
        >>> hpj("& /B", "C") # Not recommended
        '/B/C'
        >>> hpj("> B/C", " D/ ")
        '<path_to_repo>/B/C/D'
    """
    args = [arg.strip() for arg in args if (arg is not None) and arg.strip()]
    if len(args) == 0:
        return None
    if cm is None:
        cm = HEAVEN_CM
    args = lflat(re.split(r"(&)(/)?", arg) for arg in args)
    args = [cm.resource() if arg == "&" else arg for arg in args]
    args = [arg.rstrip(" /").strip() for arg in args if arg and arg.rstrip(" /").strip()]
    args = lflat(re.split(r"(>)(/)?", arg) for arg in args)
    args = [cm.local_dir if arg == ">" else arg for arg in args]
    args = [arg.rstrip(" /").strip() for arg in args if arg and arg.rstrip(" /").strip()]
    path = os.path.expanduser(os.path.join(*[arg for arg in args if arg]))
    return os.path.normpath(path if not abs else os.path.abspath(path))


def encrypt_config(config: Dict[str, Any], encrypt_keys: Optional[List[str]] = None) -> Dict[str, Any]:
    """\
    Encrypt sensitive information in the LLM configuration dictionary.

    Args:
        config (Dict[str, Any]): The LLM configuration dictionary to encrypt.
        encrypt_keys (Optional[List[str]]): List of keys to encrypt. If None, uses the keys specified in the global config under "core.encrypt_keys".

    Returns:
        Dict[str, Any]: The encrypted LLM configuration dictionary.
    """
    _encrypt_keys = set(HEAVEN_CM.get("core.encrypt_keys", list())) if encrypt_keys is None else set(encrypt_keys)
    config = deepcopy(config)
    for k in config:
        if k in _encrypt_keys:
            config[k] = "******"
    return config
