"""\
JSON-file-based cache backend.
"""

__all__ = [
    "JsonCache",
]

from ..utils.basic.serialize_utils import load_json, save_json
from ..utils.basic.config_utils import hpj
from ..utils.basic.hash_utils import fmt_hash
from ..utils.basic.file_utils import touch_dir, exists_file, delete_file, list_files
from .base import BaseCache

from typing import Any, Generator, Optional, Iterable, Dict


class JsonCache(BaseCache):
    """\
    An implementation of BaseCache that stores data in JSON files in a specified directory.
    Each item key:value is stored in a separate JSON file named after the key, with values serialized as JSON.
    """

    def __init__(self, path: str, exclude: Optional[Iterable[str]] = None, *args, **kwargs):
        """\
        Initialization.

        Args:
            path (str): Path to the directory where JSON files will be stored.
            exclude (Optional[Iterable[str]]): Keys to exclude from inputs when creating cache entries.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.
        """
        super().__init__(exclude=exclude, *args, **kwargs)
        self._path = hpj(path, abs=True)
        touch_dir(self._path)

    def _get_file_path(self, key: int) -> str:
        return hpj(self._path, f"{fmt_hash(key)}.json", abs=True)

    def _has(self, key: int) -> bool:
        return exists_file(self._get_file_path(key))

    def _get(self, key: int, default: Any = ...) -> Dict[str, Any]:
        return load_json(self._get_file_path(key), strict=False) or default

    def _set(self, key: int, value: Dict[str, Any]):
        save_json(value, self._get_file_path(key))

    def _remove(self, key: int):
        delete_file(self._get_file_path(key))

    def __len__(self) -> int:
        return len(list(list_files(self._path, ext="json")))

    def _itervalues(self) -> Generator[Dict[str, Any], None, None]:
        for file_path in sorted(list_files(self._path, ext="json", abs=True)):
            yield load_json(file_path, strict=False)

    def _clear(self):
        for file_path in list_files(self._path, ext="json", abs=True):
            delete_file(file_path)
