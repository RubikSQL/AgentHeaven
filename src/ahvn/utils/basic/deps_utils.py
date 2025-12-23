"""\
Dependency management and lazy loading utilities.

This module provides a clean, industrial-standard dependency management system
and utilities for lazy loading modules.
"""

__all__ = [
    "DependencyManager",
    "DependencyError",
    "OptionalDependencyError",
    "deps",
    "lazy_getattr",
    "collect_exports",
    "lazy_import_submodules",
    "DependencyInfo",
    "get_default_dependencies",
]

from typing import Dict, List, Optional, Any, Union
import importlib
import types
from dataclasses import dataclass


@dataclass
class DependencyInfo:
    """Information about a dependency."""

    name: str
    packages: List[str]
    install: str
    description: str
    optional: bool = True
    required_for: Optional[List[str]] = None

    def __post_init__(self):
        """Initialize default values."""
        if self.required_for is None:
            self.required_for = []


def get_default_dependencies() -> dict:
    """Get all default dependency definitions."""
    return {
        "mysql": DependencyInfo(
            name="mysql",
            packages=["pymysql"],
            install="pip install pymysql mysqlclient",
            description="MySQL database support",
            required_for=["database", "mysql_connections"],
        ),
        "postgresql": DependencyInfo(
            name="postgresql",
            packages=["psycopg2-binary"],
            install="pip install psycopg2-binary",
            description="PostgreSQL database support",
            required_for=["database", "postgresql_connections"],
        ),
        "duckdb": DependencyInfo(
            name="duckdb",
            packages=["duckdb"],
            install="pip install duckdb duckdb-engine",
            description="DuckDB database support",
            required_for=["database", "analytics"],
        ),
        "mssql": DependencyInfo(
            name="mssql",
            packages=["pyodbc"],
            install="pip install pyodbc",
            description="Microsoft SQL Server support",
            required_for=["database", "mssql_connections"],
        ),
        "spacy": DependencyInfo(
            name="spacy",
            packages=["spacy"],
            install="pip install spacy",
            description="spaCy NLP library",
            required_for=["nlp", "text_processing"],
        ),
        "fastmcp": DependencyInfo(
            name="fastmcp",
            packages=["fastmcp"],
            install="pip install fastmcp",
            description="FastMCP interface",
            required_for=["mcp", "interfaces"],
        ),
        "pyahocorasick": DependencyInfo(
            name="pyahocorasick",
            packages=["ahocorasick"],
            install="pip install pyahocorasick",
            description="Aho-Corasick automaton for fast string matching",
            required_for=["string_search", "pattern_matching"],
        ),
        "chromadb": DependencyInfo(
            name="chromadb",
            packages=["chromadb"],
            install="pip install chromadb",
            description="ChromaDB vector database",
            required_for=["vector_db", "chroma_integration"],
        ),
        "mongodb": DependencyInfo(
            name="mongodb",
            packages=["pymongo"],
            install="pip install pymongo",
            description="MongoDB database support",
            required_for=["database", "mongodb_connections"],
        ),
        "milvus": DependencyInfo(
            name="milvus",
            packages=["pymilvus"],
            install="pip install pymilvus",
            description="Milvus vector database",
            required_for=["vector_db", "milvus_integration"],
        ),
        "lancedb": DependencyInfo(
            name="lancedb",
            packages=["lancedb", "pyarrow"],
            install="pip install lancedb pyarrow",
            description="Lance vector database",
            required_for=["vector_db", "lance_integration"],
        ),
        "llamaindex": DependencyInfo(
            name="llamaindex",
            packages=["llama_index"],
            install="pip install llama-index llama-index-llms-ollama",
            description="LlamaIndex integration",
            required_for=["rag", "llm_integration"],
        ),
        "neo4j": DependencyInfo(
            name="neo4j",
            packages=["neo4j"],
            install="pip install neo4j",
            description="Neo4j graph database",
            required_for=["graph_db", "neo4j_integration"],
        ),
        "snowflake": DependencyInfo(
            name="snowflake",
            packages=["snowflake-sqlalchemy"],
            install="pip install snowflake-sqlalchemy",
            description="Snowflake database support",
            required_for=["database", "snowflake_connections"],
        ),
        "bigquery": DependencyInfo(
            name="bigquery",
            packages=["sqlalchemy-bigquery"],
            install="pip install sqlalchemy-bigquery",
            description="BigQuery database support",
            required_for=["database", "bigquery_connections"],
        ),
        "clickhouse": DependencyInfo(
            name="clickhouse",
            packages=["clickhouse-sqlalchemy"],
            install="pip install clickhouse-sqlalchemy",
            description="ClickHouse database support",
            required_for=["database", "clickhouse_connections"],
        ),
        "trino": DependencyInfo(
            name="trino",
            packages=["trino"],
            install="pip install trino sqlalchemy-trino",
            description="Trino database support",
            required_for=["database", "trino_connections"],
        ),
        "presto": DependencyInfo(
            name="presto",
            packages=["pyhive"],
            install="pip install pyhive",
            description="Presto database support",
            required_for=["database", "presto_connections"],
        ),
        "oracle": DependencyInfo(
            name="oracle",
            packages=["cx_Oracle"],
            install="pip install cx_Oracle sqlalchemy",
            description="Oracle database support",
            required_for=["database", "oracle_connections"],
        ),
        "databricks": DependencyInfo(
            name="databricks",
            packages=["databricks-sql-connector"],
            install="pip install databricks-sql-connector sqlalchemy-databricks",
            description="Databricks support",
            required_for=["database", "databricks_connections"],
        ),
        "hive": DependencyInfo(
            name="hive",
            packages=["pyhive"],
            install="pip install pyhive thrift sasl thrift_sasl",
            description="Hive support",
            required_for=["database", "hive_connections"],
        ),
        "starrocks": DependencyInfo(
            name="starrocks",
            packages=["starrocks"],
            install="pip install starrocks sqlalchemy-starrocks",
            description="StarRocks support",
            required_for=["database", "starrocks_connections"],
        ),
        "hana": DependencyInfo(
            name="hana",
            packages=["hdbcli"],
            install="pip install hdbcli sqlalchemy-hana",
            description="SAP HANA support",
            required_for=["database", "hana_connections"],
        ),
        "sqlalchemy": DependencyInfo(
            name="sqlalchemy",
            packages=["sqlalchemy"],
            install="pip install sqlalchemy",
            description="SQLAlchemy ORM",
            required_for=["database", "orm"],
        ),
        "sqlglot": DependencyInfo(
            name="sqlglot",
            packages=["sqlglot"],
            install="pip install sqlglot",
            description="SQL Parser and Transpiler",
            required_for=["database", "sql_processing"],
        ),
        "prettytable": DependencyInfo(
            name="prettytable",
            packages=["prettytable"],
            install="pip install prettytable",
            description="Table display utility",
            required_for=["cli", "display"],
        ),
        "litellm": DependencyInfo(
            name="litellm",
            packages=["litellm"],
            install="pip install litellm",
            description="LLM interface",
            required_for=["llm"],
        ),
        "pandas": DependencyInfo(
            name="pandas",
            packages=["pandas"],
            install="pip install pandas",
            description="Data analysis library",
            required_for=["analytics"],
        ),
        "numpy": DependencyInfo(
            name="numpy",
            packages=["numpy"],
            install="pip install numpy",
            description="Numerical computing library",
            required_for=["analytics", "vector"],
        ),
    }


class DependencyError(Exception):
    """Dependency-related error."""

    pass


class OptionalDependencyError(DependencyError, ImportError):
    """Optional dependency not available."""

    pass


class DependencyManager:
    """Clean dependency management system."""

    _instance: Optional["DependencyManager"] = None

    def __new__(cls) -> "DependencyManager":
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the manager."""
        if hasattr(self, "_initialized"):
            return

        self._deps: Dict[str, DependencyInfo] = {}
        self._cache: Dict[str, bool] = {}

        self._load_defaults()
        self._initialized = True

    def _load_defaults(self):
        """Load default dependencies."""
        for dep_info in get_default_dependencies().values():
            self.add(dep_info)

    def add(self, dep_info: DependencyInfo) -> None:
        """Add a dependency."""
        if not dep_info.name:
            raise ValueError("Dependency name cannot be empty")
        self._deps[dep_info.name] = dep_info

    def check(self, name: str) -> bool:
        """Check if a dependency is available."""
        if name in self._cache:
            return self._cache[name]

        if name not in self._deps:
            # If not registered, try direct import check
            try:
                importlib.import_module(name)
                self._cache[name] = True
                return True
            except ImportError:
                self._cache[name] = False
                return False

        dep_info = self._deps[name]
        available = False
        for pkg in dep_info.packages:
            try:
                importlib.import_module(pkg)
                available = True
                break
            except ImportError:
                continue

        self._cache[name] = available
        return available

    def require(self, name: str, feature: str = "") -> None:
        """Require a dependency, raising error if missing."""
        if not self.check(name):
            if name in self._deps:
                dep_info = self._deps[name]
                feature_msg = f" for {feature}" if feature else ""
                raise OptionalDependencyError(f"{dep_info.description} is required{feature_msg}.\n" f"Install with: {dep_info.install}")
            else:
                feature_msg = f" for {feature}" if feature else ""
                raise OptionalDependencyError(f"Package '{name}' is required{feature_msg}.\n" f"Install with: pip install {name}")

    def list(self, filter_optional: Optional[bool] = None) -> List[str]:
        """List all dependencies."""
        deps = list(self._deps.keys())

        if filter_optional is not None:
            deps = [name for name in deps if self._deps[name].optional == filter_optional]

        return deps

    def missing(self) -> List[str]:
        """Get list of missing dependencies."""
        return [name for name in self._deps if not self.check(name)]

    def info(self, name: str) -> Dict[str, Any]:
        """Get dependency information."""
        if name not in self._deps:
            raise KeyError(f"Dependency '{name}' not found")

        dep_info = self._deps[name]
        return {
            "name": name,
            "description": dep_info.description,
            "packages": dep_info.packages,
            "install": dep_info.install,
            "optional": dep_info.optional,
            "available": self.check(name),
            "required_for": dep_info.required_for,
        }

    def clear_cache(self) -> None:
        """Clear dependency cache."""
        self._cache.clear()

    def load(
        self,
        module_name: str,
        package: Optional[str] = None,
        error_msg: Optional[str] = None,
    ) -> types.ModuleType:
        """
        Import an optional dependency, raising a clear error if missing.

        Args:
            module_name: The python module name to import (e.g. "pandas")
            package: The pip package name (e.g. "pandas"). Defaults to module_name.
            error_msg: Custom error message. If None, generates a standard one.

        Returns:
            The imported module.

        Raises:
            OptionalDependencyError: If the module cannot be imported.
        """
        try:
            return importlib.import_module(module_name)
        except ImportError as e:
            # Check if the error is actually due to the module we want, or a sub-dependency
            if e.name and e.name != module_name and not module_name.startswith(e.name + "."):
                # It's a sub-dependency error, re-raise it as is to avoid confusion
                raise

            pkg_name = package or module_name

            # Check if we have info in the registry
            if pkg_name in self._deps:
                dep_info = self._deps[pkg_name]
                install_cmd = dep_info.install
                desc = dep_info.description
            else:
                install_cmd = f"pip install {pkg_name}"
                desc = f"Package '{pkg_name}'"

            if error_msg:
                msg = f"{error_msg}\nInstall with: {install_cmd}"
            else:
                msg = f"{desc} is required but not installed.\nInstall with: {install_cmd}"

            raise OptionalDependencyError(msg) from e


# Global instance
deps = DependencyManager()


# Lazy loading utilities


def lazy_getattr(name: str, export_map: Dict[str, str], package: str):
    """\
    Helper function to implement __getattr__ for lazy loading modules.

    Args:
        name: The attribute name being accessed.
        export_map: A dictionary mapping attribute names to relative module paths (e.g., { "MyClass": ".my_module" }).
        package: The package name (usually __name__ of the calling module).

    Returns:
        The requested attribute from the imported module.

    Raises:
        AttributeError: If the name is not in the export_map.
    """
    if name in export_map:
        module_path = export_map[name]
        module = importlib.import_module(module_path, package)
        return getattr(module, name)

    raise AttributeError(f"module {package!r} has no attribute {name!r}")


def collect_exports(package_names: List[str], parent_package: str) -> Dict[str, str]:
    """\
    Collects exported names from a list of subpackages to build a master lazy map.

    Args:
        package_names: List of relative package names (e.g., ["klstore", "klengine"]).
        parent_package: The parent package name (usually __name__).

    Returns:
        A dictionary mapping exported names to their relative package path (e.g., { "DatabaseKLStore": ".klstore" }).
    """
    lazy_map = {}
    for pkg_name in package_names:
        # Import the subpackage (assumed to be lightweight/lazy itself)
        full_pkg_name = f".{pkg_name}"
        pkg = importlib.import_module(full_pkg_name, parent_package)

        # Get its __all__
        exports = getattr(pkg, "__all__", [])
        for item in exports:
            lazy_map[item] = full_pkg_name

    return lazy_map


def lazy_import_submodules(name: str, submodules: List[str], package: str):
    """\
    Helper function to lazy load submodules.

    Args:
        name: The attribute name being accessed.
        submodules: List of submodule names (relative).
        package: The package name.

    Returns:
        The imported module or None.
    """
    if name in submodules:
        return importlib.import_module(f".{name}", package)
    return None
