"""\
Database configuration utilities for AgentHeaven.

This module provides functions to parse and resolve database configurations
similar to how LLM configurations are handled. It supports multiple database
providers (SQLite, PostgreSQL, DuckDB, etc.) and generates SQLAlchemy-ready
configurations with URLs and hyperparameters.
"""

__all__ = [
    "resolve_db_config",
    "create_database_engine",
    "create_database",
    "split_sqls",
    "transpile_sql",
    "prettify_sql",
    "compare_sqls",
    "load_builtin_sql",
    "SQLProcessor",
]

from ..basic.log_utils import get_logger
from ..basic.config_utils import HEAVEN_CM, hpj
from ..basic.file_utils import touch_dir
from ..basic.debug_utils import raise_mismatch
from ..basic.cmd_utils import cmd
from ...utils.basic.parser_utils import parse_keys

from ..deps import deps

_sa = None


def get_sa():
    global _sa
    if _sa is None:
        _sa = deps.load("sqlalchemy")
    return _sa


def get_sa_engine():
    return deps.load("sqlalchemy.engine")


_sqlglot = None


def get_sqlglot():
    global _sqlglot
    if _sqlglot is None:
        _sqlglot = deps.load("sqlglot")
    return _sqlglot


import os
import re
from typing import Dict, Any, Optional, Tuple, List
from copy import deepcopy

# from urllib.parse import quote_plus

logger = get_logger(__name__)


def resolve_db_config(database: str = None, provider: str = None, pool: Dict[str, Any] = None, **kwargs) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """\
    Compile a database configuration dictionary based on the following order of priority:
    1. kwargs
    2. provider
    3. global configuration
    When a parameter is specified in multiple places, the one with the highest priority is used.
    When missing, the provider falls back to the default provider.

    Args:
        database (str, optional): The database name to use.
        provider (str, optional): The database provider name to use (e.g., 'sqlite', 'pg', 'duckdb').
        pool (Dict[str, Any], optional): Pool configuration to override provider defaults.
        **kwargs: Additional parameters to override in the configuration.

    Returns:
        Tuple[Dict[str, Any], Dict[str, Any]]:
            1. The resolved database configuration dictionary with 'url', 'pool', and hyperparameters.
            Connection parameters (dialect, driver, username, password, host, port, database)
            are used to build the URL and then removed from the final config.
            2. The connection parameters dictionary.
    """
    db_config = HEAVEN_CM.get("db", dict())
    providers_config = db_config.get("providers", dict())
    default_provider = db_config.get("default_provider", "sqlite")
    default_args = db_config.get("default_args", dict())

    args = dict()
    args.update(deepcopy(default_args))

    # Resolve provider parameters
    if not provider:
        provider = default_provider
    if provider and (provider not in providers_config):
        raise_mismatch(providers_config, got=provider, name="database provider")
    provider_config = providers_config.get(provider, dict())
    args.update(deepcopy(provider_config))

    # Resolve custom kwargs
    if database:
        args["database"] = database
    args.update(deepcopy(kwargs))

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

    # Extract connection parameters to build URL
    # SQLAlchemy compatible format:
    #   <dialect>+<driver>://<username>:<password>@<host>:<port>/<database>?<query_params>
    connection_params = {"dialect", "driver", "host", "port", "username", "password", "database", "query_params"}
    if "url" not in args:
        dialect = args.get("dialect")
        if not dialect:
            raise ValueError("Database dialect is required")
        driver = args.get("driver")
        host = args.get("host")
        port = args.get("port")
        username = args.get("username")
        password = args.get("password")
        database = args.get("database", "")
        query_params = args.get("query_params", {})
        url_parts = [dialect]
        if driver:
            url_parts.extend(["+", driver])
        url_parts.append("://")
        if username:
            url_parts.append(username)
            if password:
                url_parts.extend([":", str(password)])
            url_parts.append("@")
        if host:
            url_parts.append(host)
            if port:
                url_parts.extend([":", str(port)])
        url_parts.append("/")
        if database:
            url_parts.append(database)

        # Append query parameters from config
        if query_params:
            params_list = [f"{k}={v}" for k, v in query_params.items()]
            url_parts.append("?")
            url_parts.append("&".join(params_list))

        args["url"] = "".join(url_parts)

    # Extract pool config (from provider config, can be overridden by pool argument)
    pool_config = args.pop("pool", {})
    if pool:
        pool_config.update(pool)  # Override with explicit pool argument

    # Extract connection args before filtering
    connection_params = {"dialect", "driver", "host", "port", "username", "password", "database", "query_params"}
    connection_args = {k: v for k, v in args.items() if k in connection_params}
    connection_args["provider"] = provider  # Include provider for clone() support
    connection_args["pool"] = pool_config  # Include pool config in connection_args
    args = {k: v for k, v in args.items() if k not in connection_params}

    return args, connection_args


def create_database_engine(config: Dict[str, Any], conn_args: Optional[Dict[str, Any]], autocreate: bool = True):
    """\
    Create a SQLAlchemy engine from the resolved database configuration.

    Uses appropriate connection pooling strategy based on dialect:
    - SQLite: StaticPool (file) or SingletonThreadPool (:memory:)
    - DuckDB: NullPool (thread-safe, no pooling needed)
    - PostgreSQL/MySQL/MSSQL: QueuePool with configurable settings

    Pool settings are read from conn_args['pool'] (set by resolve_db_config from provider config).

    Args:
        config: The database configuration dictionary.
        conn_args: Connection arguments containing dialect, database, pool config, etc.
        autocreate: Whether to automatically create the database if it does not exist.

    Returns:
        Engine: A SQLAlchemy engine instance.

    Raises:
        ImportError: If SQLAlchemy is not installed.
        ValueError: If required configuration is missing.
    """
    url = config.get("url", None)
    cfg_autocreate = bool(config.get("autocreate", False))
    autocreate_flag = bool(autocreate) or cfg_autocreate
    dialect = conn_args.get("dialect", "sqlite") if conn_args else "sqlite"
    database = conn_args.get("database", "") if conn_args else ""
    pool_config = conn_args.get("pool", {}) if conn_args else {}

    # Build engine kwargs, removing control keys
    engine_kwargs = {k: v for k, v in config.items() if k not in ("url", "autocreate")}

    # Apply dialect-specific pooling strategy
    engine_kwargs = _apply_pool_strategy(engine_kwargs, dialect, database, pool_config)

    # Optionally create the target database first
    if autocreate_flag:
        try:
            create_database(config | (conn_args or {}), engine_kwargs=engine_kwargs)
        except Exception as e:
            safe_url = get_sa_engine().make_url(url).render_as_string(hide_password=True) if url else "unknown"
            logger.warning(f"Failed to autocreate database for url={safe_url}: {e}")

    return get_sa().create_engine(url, **engine_kwargs)


def _apply_pool_strategy(engine_kwargs: Dict[str, Any], dialect: str, database: str, pool_config: Dict[str, Any]) -> Dict[str, Any]:
    """\
    Apply appropriate pooling strategy based on dialect and configuration.

    Args:
        engine_kwargs: Existing engine keyword arguments.
        dialect: Database dialect.
        database: Database name/path.
        pool_config: Pool configuration from provider config.

    Returns:
        Updated engine_kwargs with pool settings.
    """
    from sqlalchemy.pool import StaticPool, NullPool, QueuePool

    kwargs = dict(engine_kwargs)

    if dialect == "sqlite":
        # SQLite: Use StaticPool for :memory: (shares single connection across threads)
        # or NullPool for file-based (SQLite handles its own locking, each thread gets fresh connection)
        if database == ":memory:":
            # :memory: requires StaticPool to share the same connection
            kwargs["poolclass"] = StaticPool
            kwargs["connect_args"] = kwargs.get("connect_args", {})
            kwargs["connect_args"]["check_same_thread"] = False
        else:
            # File-based SQLite: NullPool is safest for concurrent access
            # SQLite has its own file-level locking mechanism
            kwargs["poolclass"] = NullPool
            kwargs["connect_args"] = kwargs.get("connect_args", {})
            kwargs["connect_args"]["check_same_thread"] = False

    elif dialect == "duckdb":
        # DuckDB: thread-safe, use NullPool (no persistent connections)
        kwargs["poolclass"] = NullPool

    elif dialect in ("postgresql", "postgres", "mysql", "mssql"):
        # Server-based databases: use QueuePool with configurable settings
        kwargs["poolclass"] = QueuePool

        # Apply pool config settings
        if pool_config.get("pool_pre_ping"):
            kwargs["pool_pre_ping"] = True
        if "pool_size" in pool_config:
            kwargs["pool_size"] = pool_config["pool_size"]
        if "max_overflow" in pool_config:
            kwargs["max_overflow"] = pool_config["max_overflow"]
        if "pool_timeout" in pool_config:
            kwargs["pool_timeout"] = pool_config["pool_timeout"]
        if "pool_recycle" in pool_config and pool_config["pool_recycle"] > 0:
            kwargs["pool_recycle"] = pool_config["pool_recycle"]

    return kwargs


def create_database(config: Dict[str, Any], engine_kwargs: Optional[Dict[str, Any]] = None) -> None:
    """Create the database if it does not already exist.

    This helper supports SQLite (directory creation), PostgreSQL, and MySQL database creation.

    Args:
        config: Database configuration dict containing connection parameters.
        engine_kwargs: Optional kwargs to pass when creating temporary engines.

    Notes:
        - The function is best-effort and will log on failure; callers may choose to
            ignore failures by catching exceptions.
    """
    engine_kwargs = engine_kwargs or {}
    dialect = config.get("dialect")
    database_name = config.get("database")

    # Skip if required parameters are missing
    if not dialect or not database_name:
        return

    # Handle SQLite: ensure directory exists for file-backed DBs
    if dialect == "sqlite":
        if database_name != ":memory:":
            db_dir = os.path.dirname(database_name)
            if db_dir and not os.path.exists(db_dir):
                touch_dir(db_dir)
        return

    # Handle server-based databases (PostgreSQL, MySQL, MSSQL)
    if dialect in ("postgresql", "postgres", "mysql", "mssql"):
        _create_server_database(config, engine_kwargs)
        return

    # For other backends, nothing implemented
    logger.debug(f"autocreate not implemented for dialect={dialect}")


def _create_server_database(config: Dict[str, Any], engine_kwargs: Dict[str, Any]) -> None:
    """Create database on server-based systems (PostgreSQL, MySQL).

    Args:
        config: Database configuration dict.
        engine_kwargs: Engine creation kwargs.
    """
    dialect = config.get("dialect")
    database_name = config.get("database")

    # Create proper maintenance database config using connection parameters directly
    if dialect == "mssql":
        maintenance_config = {
            "dialect": dialect,
            "driver": config.get("driver"),
            "host": config.get("host"),
            "port": config.get("port"),
            "username": config.get("username"),
            "password": config.get("password"),
            "database": "master",  # MSSQL uses master as maintenance database
            "query_params": config.get("query_params", {}),
        }
        exists_query = "SELECT 1 FROM sys.databases WHERE name = :name"
        create_template = "CREATE DATABASE [{name}]"

        def name_escape(name):
            return name.replace("]", "]]")

    elif dialect in ("postgresql", "postgres"):
        maintenance_config = {
            "dialect": dialect,
            "driver": config.get("driver"),
            "host": config.get("host"),
            "port": config.get("port"),
            "username": config.get("username"),
            "password": config.get("password"),
            "database": "postgres",
        }
        exists_query = "SELECT 1 FROM pg_database WHERE datname = :name"
        create_template = 'CREATE DATABASE "{name}"'

        def name_escape(name):
            return name.replace('"', '""')

    elif dialect == "mysql":
        maintenance_config = {
            "dialect": dialect,
            "driver": config.get("driver"),
            "host": config.get("host"),
            "port": config.get("port"),
            "username": config.get("username"),
            "password": config.get("password"),
            "database": "",  # MySQL connects to server without specific database
        }
        exists_query = "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = :name"
        create_template = "CREATE DATABASE `{name}`"

        def name_escape(name):
            return name.replace("`", "``")

    else:
        return

    # Build maintenance database URL
    maintenance_url = _build_database_url(maintenance_config)

    # Configure engine for DDL operations
    tmp_engine_kwargs = dict(engine_kwargs)
    tmp_engine_kwargs.setdefault("isolation_level", "AUTOCOMMIT")
    tmp_engine_kwargs.setdefault("pool_timeout", 10)
    tmp_engine_kwargs.setdefault("pool_recycle", 3600)

    tmp_engine = get_sa().create_engine(maintenance_url, **tmp_engine_kwargs)

    try:
        with tmp_engine.connect() as conn:
            # Check if database exists
            exists_q = get_sa().text(exists_query)
            res = conn.execute(exists_q, {"name": database_name}).scalar()

            if not res:
                # Create database
                safe_name = name_escape(database_name)
                create_q = create_template.format(name=safe_name)

                try:
                    if dialect in ("postgresql", "postgres"):
                        # PostgreSQL needs separate connection for DDL
                        ddl_conn = tmp_engine.connect()
                        try:
                            ddl_conn.execute(get_sa().text("COMMIT"))
                            ddl_conn.execute(get_sa().text(create_q))
                            logger.info(f"Created database '{database_name}'")
                        finally:
                            ddl_conn.close()
                    elif dialect == "mssql":
                        # MSSQL can use the same connection with AUTOCOMMIT
                        conn.execute(get_sa().text(create_q))
                        logger.info(f"Created database '{database_name}'")
                    else:
                        # MySQL can use the same connection
                        conn.execute(get_sa().text(create_q))
                        logger.info(f"Created database '{database_name}'")
                except Exception as ddl_ex:
                    logger.error(f"Failed to create database '{database_name}': {ddl_ex}")
                    raise
    finally:
        try:
            tmp_engine.dispose()
        except Exception:
            pass


def _build_database_url(config: Dict[str, Any]) -> str:
    """Build SQLAlchemy URL from database config.

    Args:
        config: Database configuration dict.

    Returns:
        str: SQLAlchemy URL string.
    """
    dialect = config.get("dialect")
    driver = config.get("driver")
    host = config.get("host")
    port = config.get("port")
    username = config.get("username")
    password = config.get("password")
    database = config.get("database", "")

    url_parts = [dialect]
    if driver:
        url_parts.extend(["+", driver])
    url_parts.append("://")

    if username:
        url_parts.append(username)
        if password:
            url_parts.extend([":", str(password)])
        url_parts.append("@")

    if host:
        url_parts.append(host)
        if port:
            url_parts.extend([":", str(port)])

    url_parts.append("/")
    if database:
        url_parts.append(database)

    # Append query parameters from config
    query_params = config.get("query_params", {})
    if query_params:
        params_list = [f"{k}={v}" for k, v in query_params.items()]
        url_parts.append("?")
        url_parts.append("&".join(params_list))

    return "".join(url_parts)


def split_sqls(queries: str, dialect: str = "sqlite"):
    """\
    Split a string containing multiple SQL queries into a list.

    Args:
        queries (str): The SQL queries to split.
        dialect (str): The SQL dialect to use (default is "sqlite").

    Returns:
        List[str]: A list of individual SQL queries.
    """
    try:
        if not queries.strip():  # Handle empty or whitespace-only strings
            return []
        parsed = get_sqlglot().parse(queries, dialect=dialect)
        return [s.sql().strip() for s in parsed if s is not None]
    except Exception as e:
        raise ValueError(f"Failed to split SQL queries: {e}.")


def transpile_sql(query: str, src_dialect: str = "sqlite", tgt_dialect: str = "sqlite") -> str:
    """\
    Transpile a SQL query from one dialect to another.

    Args:
        query (str): The SQL query to transpile.
        src_dialect (str): The source dialect to transpile from.
        tgt_dialect (str): The target dialect to transpile to (default is the current dialect).

    Returns:
        str: The transpiled query.

    Raises:
        ImportError: If SQLGlot is not installed.
        ValueError: If transpilation fails.
    """
    try:
        # Handle dialect mapping
        dialect_map = {"postgresql": "postgres"}
        src = dialect_map.get(src_dialect, src_dialect)
        tgt = dialect_map.get(tgt_dialect, tgt_dialect)
        return get_sqlglot().transpile(query, read=src, write=tgt, comments=False)[0]
    except Exception as e:
        raise ValueError(f"Failed to transpile query from {src_dialect} to {tgt_dialect}: {e}.")


def prettify_sql(query: str, dialect: str = "sqlite", comments: bool = True) -> str:
    """\
    Prettify a SQL query for better readability (identify + strip).

    Args:
        query (str): The SQL query to prettify.
        dialect (str): The SQL dialect to use (default is "sqlite").
        comments (bool): Whether to keep comments in the output (default is True).

    Returns:
        str: The prettified SQL query. If failed, returns the original query stripped.
    """
    try:
        return get_sqlglot().transpile(query, read=dialect, write=dialect, identify=True, pretty=True, comments=comments)[0].strip()
    except Exception as e:
        logger.warning(f"Failed to prettify SQL query: {e}")
        return query.strip()


def compare_sqls(sql1: str, sql2: str, db) -> bool:
    """\
    Given two SQL queries, execute them on the provided database and compare their results.

    Args:
        sql1 (str): The first SQL query.
        sql2 (str): The second SQL query.
        db: The database instance with an `execute_sql` method.

    Returns:
        bool: True if the results are identical, False otherwise.
    """
    try:
        res1 = db.execute_sql(sql1)
    except Exception as e:
        logger.warning(f"Failed to execute sql1 for comparison: {e}")
        return False
    try:
        res2 = db.execute_sql(sql2)
    except Exception as e:
        logger.warning(f"Failed to execute sql2 for comparison: {e}")
        return False
    return bool(res1 == res2)


def load_builtin_sql(query_name: str, dialect: str = "sqlite", **kwargs) -> str:
    """\
    Load SQL query from file and return the query for the current dialect.

    Warning:
        This function uses string formatting (`.format(**kwargs)`) to inject parameters into the SQL query.
        This is vulnerable to SQL injection if `kwargs` contains untrusted user input.
        Only use this function with trusted input or for internal queries where parameters are controlled.
        For user-supplied values, prefer using parameterized queries supported by your database driver.

    Args:
        query_name (str): Name of the SQL file (without .sql extension).
        dialect (str): The SQL dialect to use (default is "sqlite").
        **kwargs: Additional parameters for query formatting.

    Returns:
        str: SQL query for the current dialect. None if the query is not found.

    Raises:
        FileNotFoundError: If SQL file is not found.
    """
    sql_file_path = hpj("& sqls", f"{query_name}.sql")
    try:
        with open(sql_file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
    except FileNotFoundError:
        raise FileNotFoundError(f"SQL file not found: {sql_file_path}")
    queries = parse_keys(content)
    if dialect in queries:
        return queries[dialect].format(**kwargs).strip()  # SQL Injection Warning
    else:
        return transpile_sql(queries["sqlite"].format(**kwargs).strip(), src_dialect="sqlite", tgt_dialect=dialect)


class SQLProcessor:
    """\
    Handles SQL transpilation and parameter normalization across different database dialects.

    This class centralizes all SQL processing logic including:
    - SQL dialect transpilation via SQLGlot
    - Parameter format normalization (convert all to :param format)
    - Cross-database parameter binding support
    """

    def __init__(self, target_dialect: str):
        """\
        Initialize SQL processor for a target database dialect.

        Args:
            target_dialect: Target database dialect (sqlite, postgres, mysql, duckdb, etc.)
        """
        self.target_dialect = target_dialect
        self.logger = get_logger(__name__)

    def process_query(self, query: str, params=None, transpile_from: str = None) -> tuple[str, dict]:
        """\
        Process a SQL query and parameters for execution.

        Args:
            query: Raw SQL query
            params: Query parameters (dict, tuple, list, or None)
            transpile_from: Source dialect to transpile from (if different from target)

        Returns:
            Tuple of (processed_query, normalized_params)
        """
        # Make a copy to avoid modifying the original
        processed_query = query
        processed_params = params or {}

        # Step 1: Transpile SQL if requested
        if transpile_from and transpile_from != self.target_dialect:
            try:
                processed_query = transpile_sql(processed_query, src_dialect=transpile_from, tgt_dialect=self.target_dialect)
            except Exception as e:
                self.logger.warning(f"SQL transpile failed; running original query: {e}")

        # Step 2: Normalize parameters to :param format
        processed_query, processed_params = self._normalize_parameters(processed_query, processed_params)

        return processed_query, processed_params

    def _normalize_parameters(self, query: str, params) -> tuple[str, dict]:
        """\
        Convert all parameter formats to SQLAlchemy's named :param format.

        Args:
            query: SQL query with parameters
            params: Parameters in any format

        Returns:
            Tuple of (normalized_query, normalized_params)
        """
        if params is None:
            return query, {}

        # Handle PostgreSQL-style %(name)s parameters (from SQLGlot transpilation)
        if "%(" in query and ")s" in query and isinstance(params, dict):
            query = self._convert_pg_named_params(query)

        # Handle different parameter types
        if isinstance(params, (tuple, list)):
            return self._convert_positional_params(query, params)
        elif isinstance(params, dict):
            return self._convert_named_params(query, params)
        else:
            # Single value parameter
            return self._convert_single_param(query, params)

    def _convert_pg_named_params(self, query: str) -> str:
        """\
        Convert PostgreSQL %(name)s parameters to :name format.
        """

        def replace_pg_param(match):
            param_name = match.group(1)
            return f":{param_name}"

        return re.sub(r"%\(([^)]+)\)s", replace_pg_param, query)

    def _convert_positional_params(self, query: str, params: tuple) -> tuple[str, dict]:
        """\
        Convert positional parameters (?, %s) to named parameters.
        """
        # Determine parameter style
        if "%s" in query:
            param_style = "%s"
        elif "?" in query:
            param_style = "?"
        else:
            # No positional parameters found, return as-is
            return query, {}

        # Convert to named parameters
        param_dict = {f"param_{i}": val for i, val in enumerate(params)}
        named_query = query

        # Replace positional parameters one by one
        for i in range(len(params)):
            named_query = named_query.replace(param_style, f":param_{i}", 1)

        return named_query, param_dict

    def _convert_named_params(self, query: str, params: dict) -> tuple[str, dict]:
        """\
        Convert various named parameter formats to :name format.
        """
        param_dict = {}
        named_query = query

        # Handle $-style parameters (PostgreSQL/DuckDB)
        if "$" in query:
            dollar_params = re.findall(r"\$([a-zA-Z_][a-zA-Z0-9_]*)", query)

            for param_name in dollar_params:
                if param_name in params:
                    param_dict[f"param_{param_name}"] = params[param_name]
                    named_query = named_query.replace(f"${param_name}", f":param_{param_name}")

        # Handle :name parameters (already in correct format)
        if ":" in query:
            import re

            named_params = re.findall(r":([a-zA-Z_][a-zA-Z0-9_]*)", query)

            for param_name in named_params:
                if param_name in params:
                    param_dict[param_name] = params[param_name]

        # If no special formats found, use parameters as-is
        if not param_dict:
            param_dict = params

        return named_query, param_dict

    def _convert_single_param(self, query: str, param) -> tuple[str, dict]:
        """\
        Convert single parameter to named parameter.
        """
        # Simple case: replace first ? or %s with :param_0
        if "?" in query:
            query = query.replace("?", ":param_0", 1)
            return query, {"param_0": param}
        elif "%s" in query:
            query = query.replace("%s", ":param_0", 1)
            return query, {"param_0": param}
        else:
            # No parameter placeholder found
            return query, {}
