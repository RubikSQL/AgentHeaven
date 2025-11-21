__all__ = [
    "execute_sql",
    "toolspec_factory_builtins_execute_sql",
]

from ....utils.db import Database, table_display, SQLErrorResponse
from ....utils.basic.config_utils import HEAVEN_CM
from ...base import ToolSpec
from typing import Optional, List, Dict, Any, Literal, Union
import functools


def execute_sql(db, query: str) -> Union[List[Dict[str, Any]], SQLErrorResponse]:
    """\
    Execute a SQL statement on the database and return the results.

    This function executes a SQL query using the provided Database instance.
    For SELECT queries, it returns the results as a list of dictionaries.
    For INSERT, UPDATE, DELETE queries, it returns an empty list.
    If an error occurs, it returns a SQLErrorResponse.

    Args:
        db: The Database instance to execute the query on.
        query (str): The SQL query to execute.

    Returns:
        Union[List[Dict[str, Any]], SQLErrorResponse]: The query results as a list of dictionaries,
            an empty list for write operations, or a SQLErrorResponse on error.

    Example:
        >>> db = Database(provider="sqlite", database="test.db")
        >>> result = execute_sql(db, "SELECT * FROM users LIMIT 5")
        >>> if isinstance(result, SQLErrorResponse):
        >>>     print(result.to_string())
        >>> else:
        >>>     print(result)
        [{'id': 1, 'name': 'Alice'}, {'id': 2, 'name': 'Bob'}, ...]
    """
    result = db.execute(query, autocommit=True, safe=True)
    if isinstance(result, SQLErrorResponse):
        return result
    return list() if result is None else result.to_list(row_fmt="dict")


def toolspec_factory_builtins_execute_sql(
    db: Database,
    max_rows: Optional[int] = None,
    max_width: Optional[int] = None,
    style: Optional[Literal["DEFAULT", "MARKDOWN", "PLAIN_COLUMNS", "MSWORD_FRIENDLY", "ORGMODE", "SINGLE_BORDER", "DOUBLE_BORDER", "RANDOM"]] = None,
    name: Optional[str] = "exec_sql",
    **table_display_kwargs,
) -> ToolSpec:
    """\
    Create a ToolSpec for executing SQL queries with a specific Database instance bound.

    This factory function creates a ToolSpec from the execute_sql function, binds
    the database parameter to a specific Database instance, and wraps the output
    with table_display for formatted results.

    Display parameters default to values from config (db.display section).
    Explicitly provided parameters override config defaults.

    Args:
        db (Database): The Database instance to bind to the tool.
        max_rows (int, optional): Maximum number of rows to display. Defaults to config value (`db.display.max_rows`).
        max_width (int, optional): Maximum width for each column. Defaults to config value (`db.display.max_width`).
        style (Literal, optional): The style to use for table display. Defaults to config value (`db.display.style`).
        **table_display_kwargs: Additional keyword arguments passed to table_display.

    Returns:
        ToolSpec: A ToolSpec with the database parameter bound, ready to execute SQL queries with formatted output.

    Example:
        >>> db = Database(provider="sqlite", database="test.db")
        >>> # Use config defaults
        >>> tool = toolspec_factory_builtins_execute_sql(db)
        >>> # Override specific parameters
        >>> tool = toolspec_factory_builtins_execute_sql(db, max_rows=20, style="SINGLE_BORDER")
        >>> result = tool.call(query="SELECT * FROM users LIMIT 5")
        >>> print(result)
        # Formatted table output
    """
    # Get defaults from config
    display_config = HEAVEN_CM.get("db.display", {})
    max_rows = max_rows if max_rows is not None else display_config.get("max_rows", 64)
    max_width = max_width if max_width is not None else display_config.get("max_width", 64)
    style = style if style is not None else display_config.get("style", "DEFAULT")

    # Create a wrapper function that formats the output with table_display
    @functools.wraps(execute_sql)
    def execute_sql_formatted(db, query: str) -> str:
        """\
        Execute a SQL query on the database and return formatted results.

        Args:
            db: The Database instance to execute the query on.
            query (str): The SQL query to execute.

        Returns:
            str: The query results formatted as a table string, or an error message.
        """
        result = execute_sql(db, query)

        # Handle error response
        if isinstance(result, SQLErrorResponse):
            return result.to_string(include_full=False)

        # Handle empty result
        if not result:
            return "Query executed successfully. But no rows returned."

        # Format successful result as table
        return table_display(result, max_rows=max_rows, max_width=max_width, style=style, **table_display_kwargs)

    # Create a ToolSpec from the wrapped function
    tool_spec = ToolSpec.from_function(
        func=execute_sql_formatted,
        parse_docstring=True,
        description="Execute a SQL query on the database and return the results as a formatted table.",
        name=name,
    )

    # Bind the db parameter to the specific Database instance
    tool_spec.bind(param="db", state_key=None, default=db)

    return tool_spec
