"""
Configuration loader for test fixtures from tests.json.

This module loads and parses the JSON-based test configuration,
providing accessor methods for each component type.
"""

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from ahvn.utils import fmt_short_hash


class TestConfigLoader:
    """Load and parse tests.json configuration file."""

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize the config loader.

        Args:
            config_path: Path to tests.json. Defaults to tests/tests.json.
        """
        if config_path is None:
            # Default to tests/tests.json
            tests_dir = Path(__file__).resolve().parents[1]
            config_path = tests_dir / "tests.json"

        self.config_path = config_path
        self._config: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from JSON file."""
        with open(self.config_path, "r") as f:
            self._config = json.load(f)

    def _resolve_path(self, path_template: Optional[str], test_name: str) -> Optional[str]:
        """
        Resolve path template with test name.

        Args:
            path_template: Path template with {name} placeholder
            test_name: Test name to substitute

        Returns:
            Resolved path or None if path_template is None
        """
        if path_template is None:
            return None
        # Use a short, stable hash as the substituted name to avoid overly long
        # filesystem/database names (some backends limit name lengths).
        short_name = fmt_short_hash(test_name, length=8)
        return path_template.replace("{name}", short_name)

    def _is_commented(self, config: List[Any]) -> bool:
        """
        Check if a configuration entry is commented out.

        A config is considered commented if its first element is a string
        starting with "// " (e.g., "// MongoKLEngine").

        Args:
            config: Configuration list

        Returns:
            True if the config is commented out, False otherwise
        """
        if not config or not isinstance(config, list):
            return False
        first_elem = config[0]
        return isinstance(first_elem, str) and first_elem.startswith("// ")

    def get_cache_configs(self, test_name: Optional[str] = None) -> List[Tuple[str, Any]]:
        """
        Get cache configurations.

        Args:
            test_name: Test name for path resolution. If None, generates unique name.

        Returns:
            List of (cache_type, backend, path) tuples
        """
        if test_name is None:
            test_name = f"test_{uuid.uuid4().hex[:8]}"

        configs = []
        for config in self._config.get("cache", []):
            if self._is_commented(config):
                continue
            cache_type, backend, path = config
            resolved_path = self._resolve_path(path, test_name)
            configs.append((cache_type, backend, resolved_path))
        return configs

    def get_db_configs(self, test_name: Optional[str] = None) -> List[Tuple[str, Optional[str]]]:
        """
        Get database configurations.

        Args:
            test_name: Test name for path resolution. If None, generates unique name.

        Returns:
            List of (backend, path) tuples
        """
        if test_name is None:
            test_name = f"test_{uuid.uuid4().hex[:8]}"

        configs = []
        for config in self._config.get("db", []):
            if self._is_commented(config):
                continue
            backend, path = config
            resolved_path = self._resolve_path(path, test_name)
            configs.append((backend, resolved_path))
        return configs

    def get_vdb_configs(self, test_name: Optional[str] = None) -> List[Tuple[str, Optional[str]]]:
        """
        Get vector database configurations.

        Args:
            test_name: Test name for path resolution. If None, generates unique name.

        Returns:
            List of (backend, path) tuples
        """
        if test_name is None:
            test_name = f"test_{uuid.uuid4().hex[:8]}"

        configs = []
        for config in self._config.get("vdb", []):
            if self._is_commented(config):
                continue
            backend, path = config
            resolved_path = self._resolve_path(path, test_name)
            configs.append((backend, resolved_path))
        return configs

    def get_mdb_configs(self, test_name: Optional[str] = None) -> List[str]:
        """
        Get MongoDB configurations.

        Args:
            test_name: Test name for path resolution. If None, generates unique name.

        Returns:
            List of database names (strings)
        """
        if test_name is None:
            test_name = f"test_{uuid.uuid4().hex[:8]}"

        configs = []
        for config in self._config.get("mdb", []):
            if self._is_commented(config):
                continue
            # config is a [db_name, collection_name] list
            db_name, collection_name = config
            resolved_db = self._resolve_path(db_name, test_name)
            resolved_collection = self._resolve_path(collection_name, test_name)
            configs.append((resolved_db, resolved_collection))
        return configs

    def get_klstore_configs(self, test_name: Optional[str] = None) -> List[Tuple[str, List[Any]]]:
        """
        Get KLStore configurations.

        Args:
            test_name: Test name for path resolution. If None, generates unique name.

        Returns:
            List of (store_type, backend_args) tuples
        """
        if test_name is None:
            test_name = f"test_{uuid.uuid4().hex[:8]}"

        configs = []
        for config in self._config.get("klstore", []):
            if self._is_commented(config):
                continue
            store_type, backend_args = config
            # Resolve paths in backend_args recursively
            resolved_args = self._resolve_backend_args(backend_args, test_name)
            configs.append((store_type, resolved_args))
        return configs

    def get_klengine_configs(self, test_name: Optional[str] = None) -> List[Tuple[str, List[Any], Any, bool]]:
        """
        Get KLEngine configurations.

        Args:
            test_name: Test name for path resolution. If None, generates unique name.

        Returns:
            List of (engine_type, store_args, engine_backend_args, inplace) tuples
        """
        if test_name is None:
            test_name = f"test_{uuid.uuid4().hex[:8]}"

        configs = []
        for config in self._config.get("klengine", []):
            if self._is_commented(config):
                continue
            engine_type, store_args, engine_backend_args, inplace = config
            # Resolve paths in store_args and engine_backend_args
            resolved_store_args = self._resolve_backend_args(store_args, test_name)
            resolved_engine_args = self._resolve_backend_args(engine_backend_args, test_name) if engine_backend_args else None
            configs.append((engine_type, resolved_store_args, resolved_engine_args, inplace))
        return configs

    def _resolve_backend_args(self, args: Any, test_name: str) -> Any:
        """
        Recursively resolve paths in backend arguments.

        Args:
            args: Backend arguments (can be nested lists/dicts)
            test_name: Test name for path resolution

        Returns:
            Resolved arguments
        """
        if isinstance(args, list):
            return [self._resolve_backend_args(item, test_name) for item in args]
        elif isinstance(args, dict):
            return {k: self._resolve_backend_args(v, test_name) for k, v in args.items()}
        elif isinstance(args, str):
            return self._resolve_path(args, test_name)
        else:
            return args

    def get_config_id(self, config_type: str, config: Any) -> str:
        """
        Generate a unique test ID for a configuration.

        Args:
            config_type: Type of configuration (cache, db, vdb, klstore, klengine)
            config: Configuration tuple

        Returns:
            Unique test ID string
        """
        if config_type == "cache":
            cache_type, backend, path = config
            if backend is None:
                return cache_type.lower()
            elif path is None or path == ":memory:":
                return f"{cache_type.lower()}_{backend}_memory"
            else:
                path_suffix = Path(path).stem if isinstance(path, str) else "custom"
                return f"{cache_type.lower()}_{backend}_{path_suffix}"

        elif config_type == "db":
            backend, path = config
            if path == ":memory:":
                return f"{backend}_memory"
            elif path is None:
                return f"{backend}_default"
            else:
                path_suffix = Path(path).stem if isinstance(path, str) else "custom"
                return f"{backend}_{path_suffix}"

        elif config_type == "vdb":
            backend, path = config
            if path is None:
                return f"{backend}_default"
            else:
                path_suffix = Path(path).name if isinstance(path, str) else "custom"
                return f"{backend}_{path_suffix}"

        elif config_type == "mdb":
            db_name, collection_name = config
            db_suffix = Path(db_name).stem if isinstance(db_name, str) else "custom_db"
            collection_suffix = Path(collection_name).stem if isinstance(collection_name, str) else "custom_coll"
            return f"mdb_{db_suffix}_{collection_suffix}"

        elif config_type == "klstore":
            store_type, backend_args = config
            backend_id = self._get_backend_id(backend_args)
            return f"{store_type.lower()}_{backend_id}"

        elif config_type == "klengine":
            engine_type, store_args, engine_backend_args, inplace = config
            store_id = self._get_backend_id(store_args)
            inplace_suffix = "inplace" if inplace else "notinplace"
            return f"{engine_type.lower()}_{store_id}_{inplace_suffix}"

        else:
            raise ValueError(f"Unknown config type: {config_type}")

    def _get_backend_id(self, backend_args: Any) -> str:
        """Generate a short ID from backend arguments."""
        if isinstance(backend_args, list) and len(backend_args) > 0:
            # For nested configs like ["CacheKLStore", ["InMemCache", null, null]]
            if isinstance(backend_args[0], str):
                base_type = backend_args[0].replace("KLStore", "").replace("Cache", "").lower()
                if len(backend_args) > 1 and isinstance(backend_args[1], list):
                    nested_id = self._get_backend_id(backend_args[1])
                    return f"{base_type}_{nested_id}"
                elif len(backend_args) > 1:
                    return f"{base_type}_{str(backend_args[1])[:10]}"
                return base_type
            else:
                return "_".join(str(arg)[:10] for arg in backend_args if arg is not None)
        elif isinstance(backend_args, str):
            return backend_args[:15]
        else:
            return "default"
