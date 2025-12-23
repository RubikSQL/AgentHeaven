__all__ = [
    "SQLResponse",
    "SQLErrorResponse",
    "DatabaseErrorHandler",
    "Database",
    "table_display",
]

from .db_utils import *
from ..basic.request_utils import NetworkProxy
from ..basic.log_utils import get_logger
from ..basic.debug_utils import error_str, raise_mismatch, DatabaseError
from typing import Iterable, List, Dict, Tuple, Any, Union, Optional, Literal, Generator
from copy import deepcopy

from ..deps import deps

_sa = None
_prettytable = None


def get_sa():
    global _sa
    if _sa is None:
        _sa = deps.load("sqlalchemy")
    return _sa


def get_sa_elements():
    return deps.load("sqlalchemy.sql.elements")


def get_sa_schema():
    return deps.load("sqlalchemy.schema")


_prettytable = None


def get_prettytable():
    global _prettytable
    if _prettytable is None:
        _prettytable = deps.load("prettytable")
    return _prettytable


logger = get_logger(__name__)


class SQLResponse:
    """\
    Enhanced result wrapper for SQLAlchemy CursorResult with convenient data access methods.
    """

    def __init__(self, cursor_result):
        self._result = cursor_result
        self._fetched_data = None
        self._columns = None
        self._row_count = None
        self._lastrowid = None
        self._fetch()

    @property
    def raw(self):
        """\
        Access the underlying SQLAlchemy CursorResult.

        Returns:
            CursorResult: The underlying SQLAlchemy CursorResult.

        Warning:
            When a connection is closed, the cursor result may no longer be available.
        """
        return self._result

    @property
    def columns(self) -> List[str]:
        """\
        Get column names from the result.

        Returns:
            List[str]: The list of column names. If the result is not available, returns an empty list.
        """
        return deepcopy(self._columns)

    def _fetch(self):
        if self._fetched_data is None:
            try:
                self._fetched_data = list()
                rows = self._result.fetchall()
                for row in rows:
                    if hasattr(row, "_mapping"):
                        self._fetched_data.append(dict(row._mapping))
                    else:
                        self._fetched_data.append(dict(zip(self.columns, row)))
            except Exception as e:
                logger.debug(f"Failed to fetch result (likely DDL operation): {error_str(e)}")
                self._fetched_data = list()
        if self._columns is None:
            try:
                self._columns = list(self._result.keys()) if hasattr(self._result, "keys") else list()
            except Exception as e:
                logger.debug(f"Failed to get columns (likely DDL operation): {error_str(e)}")
                self._columns = list()
        if self._row_count is None:
            try:
                self._row_count = getattr(self._result, "row_count", -1)
            except Exception as e:
                logger.debug(f"Failed to get row count: {error_str(e)}")
                self._row_count = -1
        if self._lastrowid is None:
            try:
                self._lastrowid = getattr(self._result, "lastrowid", None)
            except Exception as e:
                logger.debug(f"Failed to get last row ID: {error_str(e)}")
                self._lastrowid = None

    @property
    def row_count(self) -> int:
        """\
        Get the number of affected rows.

        Returns:
            int: The number of affected rows. If the result is not available, returns -1.
        """
        return self._row_count

    @property
    def lastrowid(self) -> Optional[int]:
        """\
        Get the last inserted row ID.

        Returns:
            Optional[int]: The last inserted row ID. If the result is not available, returns None.
        """
        return self._lastrowid

    def fetchall(self) -> Generator[Dict[str, Any], None, None]:
        """\
        Fetch all rows as a list of dictionaries.

        Yields:
            Dict[str, Any]: The next row as a dictionary.
        """
        yield from self._fetched_data
        return

    def _get_col_enums(self, row: Dict[str, Any], column_spec: Union[str, int]) -> Any:
        """Extract column value from row by name or index."""
        if isinstance(column_spec, str):
            if column_spec not in row:
                raise ValueError(f"Column '{column_spec}' not found in row")
            return row[column_spec]
        elif isinstance(column_spec, int):
            row_values = tuple(row.values())
            if not (-len(row_values) <= column_spec < len(row_values)):
                raise ValueError(f"Column index {column_spec} out of range for row with {len(row_values)} columns")
            return row_values[column_spec]
        else:
            raise ValueError(f"Invalid column specification: {column_spec}")

    def __getitem__(self, idx: Union[int, slice, Tuple[Union[int, slice], Union[int, str]]]) -> Any:
        if isinstance(idx, (slice, int)):
            return self._fetched_data[idx]
        if isinstance(idx, tuple) and len(idx) == 2:
            row_spec, col_spec = idx
            if isinstance(row_spec, int):
                row = self._fetched_data[row_spec]
                return self._get_col_enums(row, col_spec)
            elif isinstance(row_spec, slice):
                rows = self._fetched_data[row_spec]
                return [self._get_col_enums(row, col_spec) for row in rows]
            else:
                raise ValueError(f"Invalid row specification: {row_spec}")
        raise ValueError(f"Invalid index: {idx}")

    def __len__(self) -> int:
        """\
        Get the number of rows in the result.

        Returns:
            int: The number of rows in the result.
        """
        return len(self._fetched_data)

    def to_list(self, row_fmt: Literal["dict", "tuple"] = "dict") -> Union[List[Tuple], List[Dict[str, Any]]]:
        """\
        Convert result to list of tuples.

        Args:
            row_fmt (Literal['dict', 'tuple']): The format for the rows.

        Returns:
            Union[List[Tuple], List[Dict[str, Any]]]: The result as a list of tuples or dictionaries.
        """
        if row_fmt == "dict":
            return deepcopy(self._fetched_data)
        if row_fmt == "tuple":
            return [tuple(row.values()) for row in self._fetched_data]
        raise_mismatch(["dict", "tuple"], got=row_fmt, name="row format")

    def close(self):
        """\
        Close the result cursor.
        """
        try:
            self._result.close()
        except Exception as e:
            logger.warning(f"Failed to close result cursor: {error_str(e)}")


class DatabaseErrorHandler:
    """\
    Extensible handler for database errors with type-specific processing.

    This class provides a clean way to handle different types of database errors,
    extract relevant information, and provide helpful suggestions to users.
    """

    def __init__(self, db: Optional["Database"] = None):
        """\
        Initialize the error handler.

        Args:
            db (Database, optional): Database instance for context-aware suggestions.
        """
        self.db = db
        self._handlers = {}
        self._register_default_handlers()

    def _register_default_handlers(self):
        """\
        Register default error handlers for common SQLAlchemy exceptions.
        """
        import sqlalchemy.exc as sa_exc

        self.register_handler(sa_exc.OperationalError, self._handle_operational_error)
        self.register_handler(sa_exc.ProgrammingError, self._handle_programming_error)
        self.register_handler(sa_exc.IntegrityError, self._handle_integrity_error)
        self.register_handler(sa_exc.DataError, self._handle_data_error)

    def register_handler(self, exception_type: type, handler_func):
        """\
        Register a custom handler for a specific exception type.

        Args:
            exception_type (type): The exception type to handle.
            handler_func (callable): Function that takes (exception, query, params) and returns (error_type, short_message).
        """
        self._handlers[exception_type] = handler_func

    def _add_suggestions(self, error_msg: str, pattern: str, get_options_func) -> str:
        """Add suggestions to error message (matching raise_mismatch format, excluding first line)."""
        import re
        from difflib import SequenceMatcher

        match = re.search(pattern, error_msg, re.IGNORECASE)
        if not match or not self.db:
            return error_msg

        item_name = match.group(1)
        try:
            options = get_options_func()
            # Find best match using same logic as raise_mismatch

            def similarity(a, b):
                return SequenceMatcher(None, str(a), str(b)).ratio()

            sorted_options = sorted(options, key=lambda x: similarity(item_name, x), reverse=True)
            suggestion = sorted_options[0] if sorted_options and similarity(item_name, sorted_options[0]) >= 0.3 else None

            # Build message lines (same as raise_mismatch, but skip first line)
            if suggestion:
                lines = [f"Did you mean '{suggestion}'?"]
            else:
                lines = []
            lines.append(f"Available options: {', '.join(repr(opt) for opt in options)}.")

            return error_msg + "\n" + "\n".join(lines)
        except Exception:
            pass

        return error_msg

    def _handle_operational_error(self, e: Exception, query: Optional[str], params: Optional[Any]) -> tuple:
        """Handle SQLAlchemy OperationalError exceptions."""
        orig = getattr(e, "orig", None)
        error_msg = str(orig) if orig else str(e)

        # Table not found
        if "no such table" in error_msg.lower():
            msg = self._add_suggestions(error_msg, r"no such table:\s*(\w+)", self.db.db_tabs if self.db else lambda: [])
            return "TableNotFound", msg

        # Column not found (no suggestions - would need table context)
        if "no such column" in error_msg.lower():
            return "ColumnNotFound", error_msg

        # Database locked
        if "database is locked" in error_msg.lower():
            return "DatabaseLocked", error_msg

        # Disk I/O error
        if "disk i/o error" in error_msg.lower():
            return "DiskIOError", error_msg

        return "OperationalError", error_msg

    def _handle_programming_error(self, e: Exception, query: Optional[str], params: Optional[Any]) -> tuple:
        """Handle SQLAlchemy ProgrammingError exceptions (typically syntax errors)."""
        orig = getattr(e, "orig", None)
        error_msg = str(orig) if orig else str(e)

        if "syntax error" in error_msg.lower() or "parser error" in error_msg.lower():
            return "SyntaxError", error_msg
        return "ProgrammingError", error_msg

    def _handle_integrity_error(self, e: Exception, query: Optional[str], params: Optional[Any]) -> tuple:
        """Handle SQLAlchemy IntegrityError exceptions (constraint violations)."""
        orig = getattr(e, "orig", None)
        error_msg = str(orig) if orig else str(e)

        if "foreign key constraint" in error_msg.lower():
            return "ForeignKeyViolation", error_msg
        if "unique constraint" in error_msg.lower() or "not unique" in error_msg.lower():
            return "UniqueViolation", error_msg
        if "not null constraint" in error_msg.lower() or "may not be null" in error_msg.lower():
            return "NotNullViolation", error_msg
        return "IntegrityError", error_msg

    def _handle_data_error(self, e: Exception, query: Optional[str], params: Optional[Any]) -> tuple:
        """Handle SQLAlchemy DataError exceptions (data type/value issues)."""
        orig = getattr(e, "orig", None)
        return "DataError", str(orig) if orig else str(e)

    def handle(self, e: Exception, query: Optional[str] = None, params: Optional[Any] = None) -> tuple:
        """
        Handle a database exception and extract structured error information.

        Returns:
            tuple: (error_type, short_message, full_message) extracted from the exception.
        """
        orig = getattr(e, "orig", None)
        full_msg = str(orig) if orig else str(e)

        # Find and use the appropriate handler
        for exc_type, handler in self._handlers.items():
            if isinstance(e, exc_type):
                error_type, short_msg = handler(e, query, params)
                return error_type, short_msg, full_msg

        # Fallback for unhandled exception types
        return "UnknownError", str(e), full_msg


class SQLErrorResponse:
    """\
    Structured error response for database operation failures.

    This class provides a clean, structured way to return error information
    from database operations, making it easier for LLMs and tools to handle
    and present errors to users.
    """

    def __init__(
        self,
        error_type: str,
        short_message: str,
        full_message: str,
        query: Optional[str] = None,
        params: Optional[Union[Dict[str, Any], List, Tuple]] = None,
    ):
        """\
        Initialize a SQL error response.

        Args:
            error_type (str): The type/category of error (e.g., "TableNotFound", "SyntaxError").
            short_message (str): A brief, human-readable error message.
            full_message (str): The complete error message with traceback.
            query (str, optional): The SQL query that caused the error.
            params (Union[Dict, List, Tuple], optional): The parameters used with the query.
        """
        self.error_type = error_type
        self.short_message = short_message
        self.full_message = full_message
        self.query = query
        self.params = params

    def to_string(self, include_full: bool = False) -> str:
        """\
        Format the error as a user-friendly string.

        Args:
            include_full (bool): Whether to include the full original error message. Defaults to False.

        Returns:
            str: Formatted error message.
        """
        lines = [
            "Database query execution failed.",
            f"Error Type: {self.error_type}",
            f"Error: {self.short_message}",
        ]

        if self.query:
            lines.append(f"Query: {self.query}")

        if self.params:
            lines.append(f"Params: {self.params}")

        if include_full and self.full_message != self.short_message:
            lines.append(f"Original Error: {self.full_message}")

        return "\n".join(lines)

    def __str__(self) -> str:
        return self.to_string(include_full=False)

    def __repr__(self) -> str:
        return f"SQLErrorResponse(error_type={self.error_type!r}, short_message={self.short_message!r})"


class Database(object):
    """\
    Universal Database Connector

    Provides a clean, intuitive interface for database operations across different providers
    (SQLite, PostgreSQL, DuckDB, MySQL) with standard connection management:

    1. **Basic Usage**:
        ```python
        db = Database(provider="sqlite", database=":memory:")
        result = db.execute("SELECT * FROM table")
        ```

    2. **Context Manager** (recommended for transactions):
        ```python
        with Database(provider="pg", database="mydb") as db:
            db.execute("INSERT INTO users (name) VALUES (:name)", params={"name": "Alice"})
            db.execute("UPDATE users SET active = TRUE WHERE name = :name", params={"name": "Alice"})
            # Automatically commits on success, rolls back on exception
        ```

    3. **Manual Transaction Control**:
        ```python
        db = Database(provider="sqlite", database="mydb")
        try:
            db.execute("INSERT INTO users (name) VALUES (:name)", params={"name": "Bob"}, autocommit=False)
            db.execute("UPDATE users SET active = TRUE WHERE name = :name)", params={"name": "Bob"}, autocommit=False)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close_conn()
        ```

    The class automatically handles:
    - Database creation (PostgreSQL auto-creation if database doesn't exist)
    - Connection lifecycle management
    - SQL transpilation between different database dialects
    """

    def __init__(
        self,
        database: Optional[str] = None,
        provider: Optional[str] = None,
        pool: Optional[Dict[str, Any]] = None,
        connect: bool = False,
        **kwargs,
    ):
        """\
        Initialize database connection.

        Args:
            database: Database name or path (':memory:' for in-memory)
            provider: Database provider ('sqlite', 'pg', 'duckdb', etc.)
            pool: Pool configuration to override provider defaults (e.g., {'pool_size': 10})
            connect: Whether to establish a connection immediately (default: False)
            **kwargs: Additional connection parameters
        """
        super().__init__()
        self.config, self.config_conn_args = resolve_db_config(database=database, provider=provider, pool=pool, **kwargs)
        self.dialect = self.config_conn_args.get("dialect", None)
        self.proxy = NetworkProxy(
            http_proxy=self.config.pop("http_proxy", None),
            https_proxy=self.config.pop("https_proxy", None),
        )
        self.sql_processor = SQLProcessor(self.dialect)
        self._in_context_manager = False
        self._init(connect=connect)

    def __post_init__(self):  # ad-hoc fix for dataclass
        if self.dialect == "sqlite":
            self.execute("PRAGMA foreign_keys = ON;", autocommit=True)

    def _init(self, connect: bool = False):
        self.engine = create_database_engine(self.config, conn_args=self.config_conn_args)
        self._conn = None
        if connect:
            self.connect()

    def clone(self) -> "Database":
        """\
        Create an independent Database instance with the same configuration.

        Each clone has its own connection, making it safe for parallel operations
        where each worker needs an independent database connection.

        Warning:
            For in-memory databases (`:memory:`), cloned instances do NOT share data.
            Each clone gets its own separate in-memory database.
            Use file-based databases for parallel operations requiring shared state.

        Returns:
            Database: A new independent Database instance.

        Example:
            ```python
            # Parallel-safe pattern
            def worker(db_template, task_id):
                db = db_template.clone()  # Each worker gets own connection
                try:
                    result = db.execute("SELECT * FROM tasks WHERE id = :id", params={"id": task_id})
                    return result.to_list()
                finally:
                    db.close()

            # Use with threading/multiprocessing
            with ThreadPoolExecutor() as executor:
                futures = [executor.submit(worker, db, i) for i in range(10)]
            ```
        """
        database = self.config_conn_args.get("database", "")
        if database == ":memory:":
            logger.warning(
                "Cloning an in-memory database - cloned instances will NOT share data. "
                "Each clone has its own separate in-memory database. "
                "Use a file-based database for parallel operations requiring shared state."
            )

        # Extract original parameters from config_conn_args
        return Database(
            provider=self.config_conn_args.get("provider"),
            database=database,
            pool=self.config_conn_args.get("pool"),
            connect=False,
            **{k: v for k, v in self.config_conn_args.items() if k not in ["database", "provider", "pool", "dialect", "driver", "url"]},
        )

    def connect(self):
        """\
        Establish a database connection.

        The connection pool (configured per dialect) handles:
        - Stale connection detection via pool_pre_ping
        - Connection recycling to prevent timeouts
        - Thread-safe connection management

        Returns:
            Connection: The SQLAlchemy connection object
        """
        if self._conn is None or self._conn.closed:
            with self.proxy:
                self._conn = self.engine.connect()
        return self._conn

    def close_conn(self, commit: bool = True):
        """\
        Close the database connection and return it to the pool.

        Args:
            commit: Whether to commit pending transaction before closing.
        """
        if self._conn is not None:
            try:
                if self._conn.in_transaction():
                    if commit:
                        self._conn.commit()
                    else:
                        self._conn.rollback()
            except Exception as e:
                logger.debug(f"Transaction cleanup during close: {error_str(e, tb=False)}")
            try:
                self._conn.close()
            except Exception as e:
                logger.debug(f"Connection close: {error_str(e, tb=False)}")
            finally:
                self._conn = None

    @property
    def connected(self):
        """\
        Check if database is currently connected.
        """
        return (self._conn is not None) and (not self._conn.closed)

    @property
    def conn(self):
        """\
        Get the current connection, establishing one if needed.
        """
        if not self.connected:
            self.connect()
        return self._conn

    def in_transaction(self) -> bool:
        """\
        Check if currently in a transaction.

        Returns:
            bool: True if in transaction, False otherwise
        """
        return self._conn is not None and not self._conn.closed and self._conn.in_transaction()

    def commit(self):
        """\
        Commit the current transaction.
        """
        if self.in_transaction():
            self._conn.commit()

    def rollback(self):
        """\
        Rollback the current transaction.
        """
        if self.in_transaction():
            self._conn.rollback()

    def __enter__(self):
        """\
        Context manager entry: establishes connection and begins transaction.
        """
        if not self.connected:
            self.connect()
        # Begin transaction if not already in one
        if not self.in_transaction():
            self.conn.begin()
        self._in_context_manager = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """\
        Context manager exit: commits or rolls back transaction and closes connection.
        """
        try:
            if exc_type is not None:
                if self.in_transaction():
                    self.rollback()
            else:
                if self.in_transaction():
                    self.commit()
        finally:
            self.close_conn(commit=False)  # Don't commit again, already handled above
            self._in_context_manager = False
        return False

    def orm_execute(
        self,
        query,
        autocommit: Optional[bool] = False,
        **kwargs,
    ) -> Union[SQLResponse, None]:
        """
        Execute a SQLAlchemy ORM query or statement.

        Args:
            query: SQLAlchemy ORM statement or ClauseElement
            autocommit: Whether to run in autocommit mode (default: False - no commits after execution)
            **kwargs: Additional keyword arguments for query execution

        Returns:
            SQLResponse: Enhanced result wrapper with convenient data access
            None: For operations that don't return results (e.g., INSERT, UPDATE, DELETE)

        Examples:
            # Using SQLAlchemy ORM statements
            from sqlalchemy import select, insert, update, delete
            from sqlalchemy.sql import text

            # Select statement
            stmt = select(users_table).where(users_table.c.id == 1)
            result = db.orm_execute(stmt)

            # Insert statement
            stmt = insert(users_table).values(name="Alice")
            db.orm_execute(stmt, autocommit=True)

            # Update statement
            stmt = update(users_table).where(users_table.c.id == 1).values(name="Bob")
            db.orm_execute(stmt, autocommit=True)

            # Delete statement
            stmt = delete(users_table).where(users_table.c.id == 1)
            db.orm_execute(stmt, autocommit=True)

            # DDL operations
            from sqlalchemy import MetaData, Table
            metadata = MetaData()
            table = Table('users', metadata, autoload_with=engine)
            table.drop(engine)  # This should work without literal_binds
        """

        if not isinstance(query, get_sa_elements().ClauseElement):
            raise ValueError("orm_execute only accepts SQLAlchemy ORM statements (ClauseElement)")

        try:
            if isinstance(query, get_sa_schema().DDLElement) or hasattr(query, "_is_ddl"):
                return self._exec_sql(query, params=None, autocommit=autocommit)
            else:
                # query = query.compile(bind=self.engine, compile_kwargs={"literal_binds": True})
                return self._exec_sql(query, params=None, autocommit=autocommit)
        except Exception as e:
            logger.debug(f"ORM Query: {query}")
            logger.error(f"Database ORM execution failed:\n{error_str(e)}")
            raise DatabaseError(f"\nDatabase ORM execution failed:\n{error_str(e)}\nQuery: {query}\n")
        finally:
            pass

    def execute(
        self,
        query: str,
        transpile: Optional[str] = None,
        autocommit: Optional[bool] = False,
        params: Optional[Union[Dict[str, Any], List[Dict[str, Any]], Tuple]] = None,
        safe: bool = False,
        **kwargs,
    ) -> Union[SQLResponse, SQLErrorResponse, None]:
        """
        Execute a raw SQL query against the database.

        Args:
            query: The SQL query to execute (raw SQL string)
            transpile: Source dialect to transpile from (if different from target)
            autocommit: Whether to run in autocommit mode (default: False - no commits after execution)
            params: Query parameters (dict for named, tuple/list for positional)
            safe: If True, returns SQLErrorResponse on error instead of raising exception (default: False)
            **kwargs: Additional keyword arguments for query execution

        Returns:
            SQLResponse: Enhanced result wrapper with convenient data access
            SQLErrorResponse: Structured error response (only if safe=True)
            None: For operations that don't return results (e.g., INSERT, UPDATE, DELETE)

        Examples:
            # Simple query (uses temporary connection with autocommit)
            result = db.execute("SELECT * FROM users")
            rows = list(result.fetchall())

            # Parameterized query
            result = db.execute("SELECT * FROM users WHERE id = :id", params={"id": 1})

            # Parameterized insert
            db.execute(
                "INSERT INTO users (name) VALUES (:name)",
                params={"name": "Alice"}
            )

            # Transactional operation
            with db:
                db.execute("INSERT INTO users (name) VALUES (:name)", params={"name": "Bob"})
                db.execute("UPDATE users SET active = TRUE WHERE name = :name", params={"name": "Bob"})

            # Cross-database SQL (transpile from PostgreSQL to the current database dialect, i.e., SQLite)
            result = db.execute("SELECT * FROM users LIMIT 10", transpile="postgresql")

            # Safe mode - returns error instead of raising
            result = db.execute("SELECT * FROM nonexistent", safe=True)
            if isinstance(result, SQLErrorResponse):
                print(result.to_string())

        Note:
            For SQLAlchemy ORM operations, use orm_execute() method instead.
        """
        # If user passes a ClauseElement to execute(), redirect to orm_execute
        # but don't pass params since ClauseElement should have its own parameters
        if isinstance(query, get_sa_elements().ClauseElement):
            if params is not None:
                logger.warning("Parameters ignored when executing ClauseElement via execute(). Use orm_execute() for ClauseElement queries.")
            return self.orm_execute(query, autocommit=autocommit, **kwargs)

        try:
            # Process string query with optional transpilation and parameters
            processed_query, processed_params = self.sql_processor.process_query(query, params, transpile_from=transpile)
            return self._exec_sql(get_sa().text(processed_query), processed_params, autocommit=autocommit, safe=safe)
        except Exception as e:
            if safe:
                # Return structured error response using the error handler
                error_handler = DatabaseErrorHandler(db=self)
                error_type, short_msg, full_msg = error_handler.handle(e, query, params)
                return SQLErrorResponse(
                    error_type=error_type,
                    short_message=short_msg,
                    full_message=full_msg,
                    query=query,
                    params=params,
                )
            else:
                # Original behavior: raise exception
                logger.debug(f"SQL Query: {query}")
                logger.debug(f"Parameters: {params}")
                logger.error(f"Database execution failed:\n{error_str(e)}")
                raise DatabaseError(f"Database execution failed:\n{e}\nQuery: {query}\nParams: {params}\n")
        finally:
            pass

    def _exec_sql(self, query, params=None, autocommit: Optional[bool] = False, safe: bool = False) -> Optional[Union[SQLResponse, SQLErrorResponse]]:
        """\
        Internal method to execute SQL queries.

        Connection pool handles stale connection recovery via pool_pre_ping.
        Transaction management:
        - autocommit=True: Execute and commit immediately (for DDL, single statements)
        - autocommit=False: Execute without commit (for use in transactions)
        - In context manager: autocommit=True is not allowed

        Args:
            query: SQLAlchemy text() or ClauseElement
            params: Query parameters
            autocommit: Whether to commit after execution
            safe: If True, re-raise exceptions for caller to handle as SQLErrorResponse

        Returns:
            SQLResponse or None
        """
        if autocommit and self._in_context_manager:
            raise DatabaseError("Cannot use `autocommit=True` within a context manager!")

        # Outside context manager: ensure clean transaction state
        if not self._in_context_manager and self.in_transaction():
            self.commit()

        try:
            # Execute the query
            result = self.conn.execute(query, params) if params else self.conn.execute(query)
            response = SQLResponse(result) if result else None

            # Commit if autocommit mode
            if autocommit:
                self.commit()

            return response

        except Exception as e:
            # Always attempt to recover from invalid transaction state
            if self._conn is not None:
                try:
                    # Try to rollback the connection directly (bypassing in_transaction check)
                    # This handles SQLAlchemy's PendingRollbackError state
                    self._conn.rollback()
                except Exception:
                    # If rollback fails, close and dispose connection
                    pass
                # Close the connection to return it to the pool in a clean state
                self.close_conn()

            if safe:
                logger.debug(f"Database execution failed (safe mode): {error_str(e, tb=False)}")
                raise
            else:
                logger.error(f"Database execution failed: {error_str(e)}")
                raise DatabaseError(f"Database execution failed: {error_str(e)}")

    # === Database Inspection Methods ===
    def db_tabs(self) -> List[str]:
        """\
        List all table names in the database.

        Returns:
            List[str]: List of table names
        """
        try:
            inspector = get_sa().inspect(self.conn)
            return inspector.get_table_names()
        except Exception as e:
            logger.warning(f"Inspector failed, falling back to SQL: {error_str(e)}")

        try:
            result = self.execute(load_builtin_sql("utils/db_tabs", dialect=self.dialect), autocommit=True)
            return [row["tab_name"] for row in result.to_list()]
        except Exception as e:
            logger.error(f"Failed to list tables: {error_str(e)}")
            return []

    def db_views(self) -> List[str]:
        """\
        List all view names in the database.

        Returns:
            List[str]: List of view names
        """
        try:
            inspector = get_sa().inspect(self.conn)
            return inspector.get_view_names()
        except Exception as e:
            logger.warning(f"Inspector failed, falling back to SQL: {error_str(e)}")

        try:
            result = self.execute(load_builtin_sql("utils/db_views", dialect=self.dialect), autocommit=True)
            return [row["view_name"] for row in result.to_list()]
        except Exception as e:
            logger.error(f"Failed to list views: {error_str(e)}")
            return []

    def tab_cols(self, tab_name: str, full_info: bool = False):
        """\
        List column information for a specific table.

        Args:
            tab_name: Name of the table
            full_info: If True, return full column information; if False, return only column names

        Returns:
            When full_info=True: List of column dictionaries with full metadata
            When full_info=False: List[str] of column names
        """
        try:
            inspector = get_sa().inspect(self.conn)
            columns = inspector.get_columns(tab_name)
            if full_info:
                return columns
            else:
                return [col["name"] for col in columns]
        except Exception as e:
            logger.warning(f"Inspector failed, falling back to SQL: {error_str(e)}")

        try:
            result = self.execute(load_builtin_sql("utils/tab_cols", dialect=self.dialect, tab_name=tab_name), autocommit=True)
            if full_info:
                return result.to_list()
            else:
                return [row["col_name"] for row in result.to_list()]
        except Exception as e:
            logger.error(f"Failed to list columns for table {tab_name}: {error_str(e)}")
            return []

    def tab_pks(self, tab_name: str) -> List[str]:
        """\
        List primary key column names for a specific table.

        Args:
            tab_name: Name of the table

        Returns:
            List[str]: List of primary key column names
        """
        try:
            inspector = get_sa().inspect(self.conn)
            pks = inspector.get_pk_constraint(tab_name)
            pk_columns = pks.get("constrained_columns", []) if pks else []
            if pk_columns:  # Only return if we found primary keys
                return pk_columns
        except Exception as e:
            logger.warning(f"Inspector failed, falling back to SQL: {error_str(e)}")

        try:
            # Standard execution for all dialects
            result = self.execute(load_builtin_sql("utils/tab_pks", dialect=self.dialect, tab_name=tab_name), autocommit=True)
            return [row["col_name"] for row in result.to_list()]
        except Exception as e:
            logger.error(f"Failed to list primary keys for table {tab_name}: {error_str(e)}")
            return []

    def tab_fks(self, tab_name: str) -> List[Dict[str, str]]:
        """\
        List foreign key information for a specific table.

        Args:
            tab_name: Name of the table

        Returns:
            List[Dict[str, str]]: List of foreign key information with keys:
                - col_name: Column name in the current table
                - tab_ref: Referenced table name
                - col_ref: Referenced column name
                - name: Foreign key constraint name
        """
        try:
            inspector = get_sa().inspect(self.conn)
            fks = inspector.get_foreign_keys(tab_name)
            result = []
            for fk in fks:
                for col, ref_col in zip(fk["constrained_columns"], fk["referred_columns"]):
                    result.append(
                        {
                            "col_name": col,
                            "tab_ref": fk["referred_table"],
                            "col_ref": ref_col,
                            "name": fk.get("name", f"FK_{col}_{fk['referred_table']}_{ref_col}"),
                        }
                    )
            return result
        except Exception as e:
            logger.warning(f"Inspector failed, falling back to SQL: {error_str(e)}")

        try:
            result = self.execute(load_builtin_sql("utils/tab_fks", dialect=self.dialect, tab_name=tab_name), autocommit=True)
            return result.to_list()
        except Exception as e:
            logger.error(f"Failed to list foreign keys for table {tab_name}: {error_str(e)}")
            return []

    def row_count(self, tab_name: str) -> int:
        """\
        Get row count for a specific table.

        Args:
            tab_name: Name of the table

        Returns:
            int: Number of rows in the table
        """
        try:
            result = self.execute(load_builtin_sql("utils/row_count", dialect=self.dialect, tab_name=tab_name), autocommit=True)
            return result.to_list()[0]["cnt"]
        except Exception as e:
            logger.error(f"Failed to count rows for table {tab_name}: {error_str(e)}")
            return 0

    def col_type(self, tab_name: str, col_name: str) -> str:
        """\
        Get column type for a specific column in a table.

        Args:
            tab_name: Name of the table
            col_name: Name of the column

        Returns:
            str: Column type
        """
        try:
            inspector = get_sa().inspect(self.conn)
            for col in inspector.get_columns(tab_name):
                if col["name"] == col_name:
                    return str(col["type"])
            raise ValueError(f"Column {col_name} not found in table {tab_name}")
        except Exception as e:
            logger.warning(f"Inspector failed, falling back to SQL: {error_str(e)}")

        try:
            result = self.execute(
                load_builtin_sql("utils/col_type", dialect=self.dialect, tab_name=tab_name, col_name=col_name),
                autocommit=True,
            )
            return result.to_list()[0]["col_type"]
        except Exception as e:
            logger.error(f"Failed to get column type for {tab_name}.{col_name}: {error_str(e)}")
            return ""

    # === Data Analysis Methods ===
    def col_distincts(self, tab_name: str, col_name: str) -> List[Any]:
        """\
        Get distinct values for a specific column.

        Args:
            tab_name: Name of the table
            col_name: Name of the column

        Returns:
            List[Any]: List of distinct values
        """
        try:
            result = self.execute(
                load_builtin_sql("utils/col_distincts", dialect=self.dialect, tab_name=tab_name, col_name=col_name),
                autocommit=True,
            )
            return [row["col_enums"] for row in result.to_list()]
        except Exception as e:
            logger.error(f"Failed to get distinct values for column {col_name} in table {tab_name}: {error_str(e)}")
            return []

    def col_enums(self, tab_name: str, col_name: str) -> List[Any]:
        """\
        Get all enumerated values for a specific column (including duplicates).

        This method returns all values from a column, including duplicates.
        For unique values only, use col_distincts() instead.

        Args:
            tab_name: Name of the table
            col_name: Name of the column

        Returns:
            List[Any]: List of all enumerated values (may contain duplicates)
        """
        try:
            result = self.execute(
                load_builtin_sql("utils/col_enums", dialect=self.dialect, tab_name=tab_name, col_name=col_name),
                autocommit=True,
            )
            return [row["col_enums"] for row in result.to_list()]
        except Exception as e:
            logger.error(f"Failed to get enumerated values for column {col_name} in table {tab_name}: {error_str(e)}")
            return []

    def col_freqs(self, tab_name: str, col_name: str) -> List[Dict[str, Any]]:
        """\
        Get value frequencies for a specific column.

        Args:
            tab_name: Name of the table
            col_name: Name of the column

        Returns:
            List[Dict[str, Any]]: List of value-frequency pairs
        """
        try:
            result = self.execute(
                load_builtin_sql("utils/col_freqs", dialect=self.dialect, tab_name=tab_name, col_name=col_name),
                autocommit=True,
            )
            return result.to_list()
        except Exception as e:
            logger.error(f"Failed to get frequencies for column {col_name} in table {tab_name}: {error_str(e)}")
            return []

    def col_freqk(self, tab_name: str, col_name: str, topk: int = 20) -> List[Dict[str, Any]]:
        """\
        Get top-k value frequencies for a specific column.

        Args:
            tab_name: Name of the table
            col_name: Name of the column
            k: Number of top values to return

        Returns:
            List[Dict[str, Any]]: List of top-k value-frequency pairs
        """
        try:
            result = self.execute(
                load_builtin_sql("utils/col_freqk", dialect=self.dialect, tab_name=tab_name, col_name=col_name, topk=topk),
                autocommit=True,
            )
            return result.to_list()
        except Exception as e:
            logger.error(f"Failed to get top-{topk} frequencies for column {col_name} in table {tab_name}: {error_str(e)}")
            return []

    def col_nonnulls(self, tab_name: str, col_name: str) -> List[Any]:
        """\
        Get list of non-null values for a specific column.

        Args:
            tab_name: Name of the table
            col_name: Name of the column

        Returns:
            List[Any]: List of non-null values
        """
        try:
            result = self.execute(
                load_builtin_sql("utils/col_nonnulls", dialect=self.dialect, tab_name=tab_name, col_name=col_name),
                autocommit=True,
            )
            return [row["col_enums"] for row in result.to_list()]
        except Exception as e:
            logger.error(f"Failed to get non-null values for column {col_name} in table {tab_name}: {error_str(e)}")
            return []

    # === Database Manipulation Methods ===
    def clear_tab(self, tab_name: str) -> None:
        """\
        Clear all data from a specific table without deleting the table itself.

        Uses SQLAlchemy ORM to ensure compatibility across all database backends.

        Args:
            tab_name: Name of the table to clear

        Raises:
            Exception: If the clearing operation fails
        """
        try:
            from sqlalchemy import MetaData, Table, delete

            metadata = MetaData()
            table = Table(tab_name, metadata, autoload_with=self.engine)
            delete_stmt = delete(table)
            self.orm_execute(delete_stmt, autocommit=True)
            logger.info(f"Cleared table: {tab_name}")
        except Exception as e:
            logger.error(f"Failed to clear table {tab_name}: {error_str(e)}")
            raise Exception(f"Table clear failed for {tab_name}: {e}")

    def drop_tab(self, tab_name: str) -> None:
        """\
        Drop a specific table from the database.

        Uses SQLAlchemy ORM to ensure compatibility across all database backends.

        Args:
            tab_name: Name of the table to drop

        Raises:
            Exception: If the drop operation fails
        """
        try:
            metadata = get_sa().MetaData()
            table = get_sa().Table(tab_name, metadata, autoload_with=self.engine)
            table.drop(self.engine)
            logger.info(f"Dropped table: {tab_name}")
        except Exception as e:
            logger.error(f"Failed to drop table {tab_name}: {error_str(e)}")
            raise Exception(f"Table drop failed for {tab_name}: {e}")

    def drop_view(self, view_name: str) -> None:
        """\
        Drop a specific view from the database.

        Args:
            view_name: Name of the view to drop

        Raises:
            Exception: If the drop operation fails
        """
        try:
            self.execute(f"DROP VIEW IF EXISTS {view_name}", autocommit=True)
            logger.info(f"Dropped view: {view_name}")
        except Exception as e:
            logger.error(f"Failed to drop view {view_name}: {error_str(e)}")
            raise Exception(f"View drop failed for {view_name}: {e}")

    def drop(self) -> None:
        """\
        Drop all tables in the database.

        Uses SQLAlchemy metadata reflection to drop all tables.

        Raises:
            DatabaseError: If the database drop operation fails
        """
        try:
            # Use SQLAlchemy metadata to reflect and drop all tables
            metadata = get_sa().MetaData()
            metadata.reflect(bind=self.engine)
            metadata.drop_all(bind=self.engine, checkfirst=True)
            logger.info("Dropped all tables using metadata")
        except Exception as e:
            logger.warning(f"Metadata drop failed, trying fallback: {error_str(e)}")
            # Fallback: try to drop tables individually
            tables = self.db_tabs()
            for table_name in tables:
                try:
                    self.drop_tab(table_name)
                except Exception as table_e:
                    logger.warning(f"Failed to drop table {table_name}: {error_str(table_e)}")
        finally:
            # Close connection and dispose engine
            self.close_conn(commit=False)
            if hasattr(self, "engine") and self.engine:
                self.engine.dispose()
                self.engine = None

    def init(self, connect: bool = True) -> None:
        """\
        Drop the entire database and create a new one.

        This method combines drop() and database creation. After dropping,
        it will recreate the database and establish a new connection.

        Raises:
            Exception: If the database initialization fails
        """
        self.drop()
        self._init(connect=connect)

    def clear(self) -> None:
        """\
        Clear all data from tables in the database without deleting the tables themselves.

        Uses the `clear_tab` method to ensure compatibility across all database backends.

        Raises:
            Exception: If the clearing operation fails
        """
        tables = self.db_tabs()
        for table_name in tables:
            try:
                self.clear_tab(table_name)
            except Exception as e:
                logger.error(f"Failed to clear table {table_name}: {error_str(e)}")

    def close(self) -> None:
        """\
        Close the database connection and dispose of the engine.
        """
        self.close_conn(commit=True)
        if hasattr(self, "engine") and self.engine:
            self.engine.dispose()
            self.engine = None


def table_display(
    table: Union["SQLResponse", Iterable[Dict]],
    schema: Optional[List[str]] = None,
    max_rows: int = 64,
    max_width: int = 64,
    style: Literal["DEFAULT", "MARKDOWN", "PLAIN_COLUMNS", "MSWORD_FRIENDLY", "ORGMODE", "SINGLE_BORDER", "DOUBLE_BORDER", "RANDOM"] = "DEFAULT",
    **kwargs,
):
    """\
    Render a tabular display of SQL query results or iterable dictionaries using PrettyTable.

    Args:
        table (Union[SQLResponse, Iterable[Dict]]): The table data to display. Can be a SQLResponse object
            (from a database query) or any iterable of dictionaries (e.g., list of dicts).
        schema (Optional[List[str]], optional): List of column names to use as the table schema. If not provided,
            the schema is inferred from the SQLResponse or from the first row of the iterable.
        max_rows (int, optional): Maximum number of rows to display (including the last row and an ellipsis row if truncated).
            If the table has more than `max_rows + 1` rows, the output will show the first `max_rows-1` rows, an ellipsis row,
            and the last row. Defaults to 64.
        max_width (int, optional): Maximum width for each column in the output table. Defaults to 64.
        style (Literal["DEFAULT", "MARKDOWN", "PLAIN_COLUMNS", "MSWORD_FRIENDLY", "ORGMODE", "SINGLE_BORDER", "DOUBLE_BORDER", "RANDOM"], optional): The style to use for the table (supported by PrettyTable). Defaults to "DEFAULT".
        **kwargs: Additional keyword arguments passed to PrettyTable.

    Returns:
        str: A string representation of the formatted table, including the number of rows in total.

    Raises:
        ValueError: If the provided table rows do not match the schema in length.

    Example:
        >>> result = db.execute("SELECT * FROM users")
        >>> table_display(result, max_rows=5)
    """
    if isinstance(table, SQLResponse):
        schema = table.columns
        table = table.to_list(row_fmt="dict")
    else:
        table = list(table)
        schema = schema or (list() if not table else list(table[0].keys()))
        if not all(len(row) == len(schema) for row in table):
            raise ValueError(f"Table failed to display. All rows must have the same number of columns as the schema.\nSchema: {schema}\nTable:\n{table}")

    # Define table styles directly
    styles = {
        "DEFAULT": get_prettytable().TableStyle.DEFAULT,
        "MARKDOWN": get_prettytable().TableStyle.MARKDOWN,
        "PLAIN_COLUMNS": get_prettytable().TableStyle.PLAIN_COLUMNS,
        "MSWORD_FRIENDLY": get_prettytable().TableStyle.MSWORD_FRIENDLY,
        "ORGMODE": get_prettytable().TableStyle.ORGMODE,
        "SINGLE_BORDER": get_prettytable().TableStyle.SINGLE_BORDER,
        "DOUBLE_BORDER": get_prettytable().TableStyle.DOUBLE_BORDER,
        "RANDOM": get_prettytable().TableStyle.RANDOM,
    }

    ptable = get_prettytable().PrettyTable(schema, **kwargs)
    ptable.set_style(styles.get(style, "DEFAULT"))
    ptable.float_format = ".6"
    ptable.max_width = max_width
    if (max_rows is not None) and (len(table) > max_rows + 1):
        bottom_cnt = max_rows // 2
        top_cnt = max_rows - bottom_cnt
        omitted_cnt = len(table) - max_rows
        for row in table[:top_cnt]:
            ptable.add_row([val for _, val in zip(schema, row.values())])
        ptable.add_row([f"... ({omitted_cnt} rows omitted)" if i == 0 else "..." for i, _ in enumerate(schema)])
        for row in table[-bottom_cnt:] if bottom_cnt > 0 else []:
            ptable.add_row([val for _, val in zip(schema, row.values())])
    else:
        for row in table:
            ptable.add_row([val for _, val in zip(schema, row.values())])

    return str(ptable) + f"\n{len(table)} rows in total."
