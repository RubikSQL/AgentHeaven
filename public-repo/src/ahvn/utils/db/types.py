"""\
ORM utilities for database operations.
"""

__all__ = [
    "Base",
    "ExportableEntity",
    "DatabaseIdType",
    "DatabaseTextType",
    "DatabaseIntegerType",
    "DatabaseBooleanType",
    "DatabaseDurationType",
    "DatabaseTimestampType",
    "DatabaseJsonType",
    "DatabaseNfType",
    "DatabaseVectorType",
]

from ..basic.config_utils import HEAVEN_CM
from ..basic.hash_utils import fmt_hash
from ..basic.serialize_utils import dumps_json, loads_json, AhvnJsonEncoder, AhvnJsonDecoder

from sqlalchemy.orm import declarative_base
from sqlalchemy.orm.attributes import instance_state
from sqlalchemy import insert, delete, select, bindparam, ARRAY as sql_ARRAY
from sqlalchemy.schema import CreateTable, DropTable
import sqlalchemy.types as sqltypes
from sqlalchemy.dialects import postgresql as sqld_postgresql, mysql as sqld_mysql, oracle as sqld_oracle
import datetime
import calendar

Base = declarative_base()


class ExportableEntity(Base):
    """\
    Base class for ORM entities with SQL export capabilities.
    """

    __abstract__ = True

    @classmethod
    def _create_stmt(cls):
        return CreateTable(cls.__table__, if_not_exists=True)

    @classmethod
    def _drop_stmt(cls):
        return DropTable(cls.__table__, if_exists=True)

    @classmethod
    def _clear_stmt(cls):
        return delete(cls)

    @classmethod
    def _exists_stmt(cls, record_id):
        return select(select(cls.id).where(cls.id == record_id).exists())

    @classmethod
    def _get_stmt(cls, record_id):
        return select(cls).where(cls.id == record_id)

    @classmethod
    def _remove_stmt(cls, condition=None, **filters):
        stmt = delete(cls)
        if condition is not None:
            stmt = stmt.where(condition)
        for col, col_value in filters.items():
            stmt = stmt.where(getattr(cls, col) == col_value)
        return stmt

    @classmethod
    def _remove_stmts(cls, **filters):
        return [cls._remove_stmt(**filters)]

    def _append_stmt(self):
        return self._insert_stmt(False)

    def _insert_stmt(self, allow_skip, condition=None):
        entity_state = instance_state(self)
        values_dict = {c.key: getattr(self, c.key) for c in self.__table__.columns if c.key in entity_state.attrs}
        if allow_skip:
            condition = condition or ~select(self.__class__.id).where(self.__class__.id == self.id).exists()
            binds = [bindparam(k, v, type_=self.__table__.columns[k].type) for k, v in values_dict.items()]
            select_stmt = select(*binds).where(condition)
            return insert(self.__class__).from_select(names=list(values_dict.keys()), select=select_stmt)
        return insert(self.__class__).values(**values_dict)

    def _upsert_stmts(self, condition=None):
        return [self.__class__._remove_stmt(id=self.id, condition=condition), self._insert_stmt(False, condition)]

    def _insert_stmts(self, condition=None):
        return [self._insert_stmt(True, condition)]

    @classmethod
    def create_stmts(cls):
        """\
        Generate a CREATE TABLE statement for this entity.

        Args:
            None

        Returns:
            ClauseElement for creating the table
        """
        return [cls._create_stmt()]

    @classmethod
    def drop_stmts(cls):
        """\
        Generate a DROP TABLE statement for this entity.

        Args:
            None

        Returns:
            ClauseElement for dropping the table
        """
        return [cls._drop_stmt()]

    @classmethod
    def clear_stmts(cls):
        """\
        Generate a DELETE statement to clear all data from this entity's table.

        Args:
            None

        Returns:
            ClauseElement for clearing all table data
        """
        return [cls._clear_stmt()]

    # Public wrapper methods
    @classmethod
    def exists_stmt(cls, record_id):
        """\
        Generate a statement to check if an entity exists by ID.

        Args:
            id: The ID of the entity to check for existence

        Returns:
            ClauseElement for checking entity existence
        """
        return cls._exists_stmt(record_id)

    @classmethod
    def get_stmt(cls, record_id):
        """\
        Generate a statement to retrieve an entity by ID.

        Args:
            id: The ID of the entity to retrieve

        Returns:
            ClauseElement for retrieving entity by ID
        """
        return cls._get_stmt(record_id)

    @classmethod
    def remove_stmts(cls, **filters):
        """\
        Generate DELETE statements for this entity based on filter criteria.

        Args:
            kwargs: Key-value pairs to filter which entities to remove

        Returns:
            List of ClauseElement objects for removing this entity
        """
        return cls._remove_stmts(**filters)

    def append_stmt(self):
        """\
        Generate INSERT statement for this entity with no conflict handling, allowing duplicates.

        Args:
            None

        Returns:
            ClauseElement for inserting this entity
        """
        return self._append_stmt()

    def upsert_stmts(self):
        """\
        Generate UPSERT statements for this entity, which forces deletion and then insertion.

        Args:
            None

        Returns:
            List of ClauseElement objects for upserting this entity
        """
        return self._upsert_stmts()

    def insert_stmts(self, condition=None):
        """\
        Generate INSERT statements for this entity, which skips existing rows.

        Args:
            condition: Optional ClauseElement to check main table existence before inserting.

        Returns:
            List of ClauseElement objects for inserting this entity
        """
        return self._insert_stmts(condition=condition)


class DatabaseIdType(sqltypes.TypeDecorator):
    """\
    md5hash-based Id type for database models.
    The ids are stored as strings but represent the integer hash of the original value.
    """

    impl = sqltypes.String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return sqltypes.String(HEAVEN_CM.get("ukf.text.id", 63))

    def process_bind_param(self, ukf_value, dialect):
        return None if ukf_value is None else fmt_hash(ukf_value)

    def process_result_value(self, db_value, dialect):
        return None if db_value is None else int(db_value)


class DatabaseTextType(sqltypes.TypeDecorator):
    """\
    Enum-like class for standard text types.
    """

    impl = sqltypes.String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "mysql" and self.length and self.length >= 16384:
            return sqld_mysql.TEXT()
        return sqltypes.String(self.length)

    def process_bind_param(self, ukf_value, dialect):
        return None if ukf_value is None else str(ukf_value)

    def process_result_value(self, db_value, dialect):
        return None if db_value is None else str(db_value)


class DatabaseIntegerType(sqltypes.TypeDecorator):
    """\
    Custom Integer type for database models.
    """

    impl = sqltypes.Integer
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return sqltypes.Integer()

    def process_bind_param(self, ukf_value, dialect):
        return None if ukf_value is None else int(ukf_value)

    def process_result_value(self, db_value, dialect):
        return None if db_value is None else int(db_value)


class DatabaseBooleanType(sqltypes.TypeDecorator):
    """\
    Custom Boolean type for database models.
    """

    impl = sqltypes.Boolean
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return sqltypes.Boolean()

    def process_bind_param(self, ukf_value, dialect):
        return None if ukf_value is None else bool(ukf_value)

    def process_result_value(self, db_value, dialect):
        return None if db_value is None else bool(db_value)


class DatabaseDurationType(sqltypes.TypeDecorator):
    """\
    Custom Duration type for database models.
    Stored as total seconds in the database.
    """

    impl = sqltypes.Integer
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return sqltypes.Integer()

    def process_bind_param(self, ukf_value, dialect):
        return None if ukf_value is None else int(ukf_value.total_seconds())

    def process_result_value(self, db_value, dialect):
        return None if db_value is None else datetime.timedelta(seconds=int(db_value))


class DatabaseJsonType(sqltypes.TypeDecorator):
    """\
    Custom Json type for database models.
    """

    impl = sqltypes.String
    cache_ok = True

    _native_dialects = {
        "postgresql": sqld_postgresql.JSONB(),
        "bigquery": sqltypes.JSON(),
        "snowflake": sqltypes.JSON(),
        "trino": sqltypes.JSON(),
        "duckdb": sqltypes.JSON(),
        "databricks": sqltypes.JSON(),
        "spark": sqltypes.JSON(),
        "presto": sqltypes.JSON(),
    }

    _string_dialects = {
        "sqlite": sqltypes.TEXT(),
        "oracle": sqld_oracle.CLOB(),
        "starrocks": sqltypes.TEXT(),
        "hana": sqld_oracle.NCLOB(),
        "hive": sqltypes.TEXT(),
        # Note: mysql and mssql have JSON types, but they do not faithfully
        # preserve very large integers during JSON serialization (e.g. >53 bits
        # or MySQL's 64-bit limits). To avoid silent precision loss we treat
        # them as string-backed JSON below.
        "mysql": sqltypes.TEXT(),
        "mssql": sqltypes.TEXT(),
    }

    def load_dialect_impl(self, dialect):
        if dialect.name in self._native_dialects:
            return dialect.type_descriptor(self._native_dialects[dialect.name])
        if dialect.name in self._string_dialects:
            return dialect.type_descriptor(self._string_dialects[dialect.name])
        return dialect.type_descriptor(sqltypes.String(HEAVEN_CM.get("ukf.text.long", 65535)))

    def process_bind_param(self, ukf_value, dialect):
        if ukf_value is None:
            return None
        if dialect.name in self._native_dialects:
            return AhvnJsonEncoder.transform(ukf_value)
        if dialect.name in self._string_dialects:
            return dumps_json(ukf_value, indent=None)
        return dumps_json(ukf_value, indent=None)

    def process_result_value(self, db_value, dialect):
        if db_value is None:
            return None
        if dialect.name in self._native_dialects:
            return AhvnJsonDecoder.transform(db_value)
        if dialect.name in self._string_dialects:
            return loads_json(db_value)
        return loads_json(db_value)


class DatabaseTimestampType(sqltypes.TypeDecorator):
    """
    Custom Timestamp type that stores UTC-converted datetimes
    as either a native timestamp or a 64-bit integer.
    """

    impl = sqltypes.BigInteger
    cache_ok = True

    _native_dialects = {
        "postgresql": sqltypes.TIMESTAMP(timezone=True),
        "mssql": sqltypes.DATETIME(),
        "oracle": sqltypes.TIMESTAMP(),
        "snowflake": sqltypes.TIMESTAMP(timezone=True),
        "bigquery": sqltypes.TIMESTAMP(),
        "duckdb": sqltypes.TIMESTAMP(),
        "trino": sqltypes.TIMESTAMP(),
        "databricks": sqltypes.TIMESTAMP(),
        "spark": sqltypes.TIMESTAMP(),
    }

    _integer_dialects = {
        "sqlite": sqltypes.BigInteger(),
        "starrocks": sqltypes.BigInteger(),
        "hive": sqltypes.BigInteger(),
        "presto": sqltypes.BigInteger(),
        "hana": sqltypes.BigInteger(),
        # Note: mysql have datetime types, but it is facing the year 2038 problem
        # on 32-bit systems. To avoid this we treat them as integer-backed timestamps below.
        "mysql": sqld_mysql.BIGINT(),
    }

    def load_dialect_impl(self, dialect):
        if dialect.name in self._native_dialects:
            return dialect.type_descriptor(self._native_dialects[dialect.name])
        if dialect.name in self._integer_dialects:
            return dialect.type_descriptor(self._integer_dialects[dialect.name])
        return dialect.type_descriptor(sqltypes.BigInteger())

    def process_bind_param(self, ukf_value, dialect):
        if ukf_value is None:
            return None
        if dialect is None or dialect.name not in self._native_dialects:
            return int(calendar.timegm(ukf_value.utctimetuple()))
        return ukf_value

    def process_result_value(self, db_value, dialect):
        if db_value is None:
            return None
        if dialect is not None and dialect.name in self._native_dialects:
            return db_value
        return datetime.datetime.fromtimestamp(db_value, tz=datetime.timezone.utc)


class DatabaseNfType(sqltypes.TypeDecorator):
    """
    A virtual type that stores data as JSON but includes normalization metadata.

    This type behaves like DatabaseJsonType for storage but provides type hints and methods
    for normalizing data into separate tables when needed. It's designed for fields
    like tags, related, auths, and synonyms that can be stored as JSON but may
    benefit from normalization for querying performance.
    """

    impl = DatabaseJsonType
    cache_ok = False

    def __init__(self, nf_schema=None, **kwargs):
        """
        Initialize DatabaseNfType.

        Args:
            nf_schema: Dict describing how to normalize this data
                Example: {
                    "columns": ["slot", "value"],
                    "types": ["short_text", "short_text"],
                    "indices": [
                        {"columns": ["ukf_id", "slot", "value"], "mysql_length": {"slot": 191, "value": 191}},
                        {"columns": ["slot", "value"], "mysql_length": {"slot": 191, "value": 191}},
                    ]
                }
        """
        super().__init__(**kwargs)
        self.nf_schema = nf_schema or {}

    def load_dialect_impl(self, dialect):
        return DatabaseJsonType().load_dialect_impl(dialect)

    def process_bind_param(self, ukf_value, dialect):
        if ukf_value is None:
            return None
        return DatabaseJsonType().process_bind_param(sorted(list(ukf_value)), dialect)

    def process_result_value(self, db_value, dialect):
        return set(DatabaseJsonType().process_result_value(db_value, dialect))


class DatabaseVectorType(sqltypes.TypeDecorator):
    """Custom Vector type for database models with pgvector support.

    Stores vector data as native PostgreSQL arrays when available (compatible with pgvector),
    or falls back to JSON serialization for other database dialects.

    Args:
        value: List, tuple, or other iterable of numeric values representing the vector.

    Returns:
        List[float]: List of floats representing the vector.

    Examples:
        >>> # PostgreSQL with native arrays
        >>> vector_type = DatabaseVectorType()
        >>> vector_type.process_bind_param([1.0, 2.0, 3.0], postgresql_dialect)
        [1.0, 2.0, 3.0]  # Stored as native array

        >>> # SQLite with JSON fallback
        >>> vector_type.process_bind_param([1.0, 2.0, 3.0], sqlite_dialect)
        '[1.0, 2.0, 3.0]'  # Stored as JSON string
    """

    impl = DatabaseJsonType
    cache_ok = True

    _native_dialects = {
        "postgresql": sql_ARRAY(sqltypes.Float()),
    }

    _json_dialects = {
        "sqlite": sqltypes.TEXT(),
        "mysql": sqltypes.TEXT(),
        "mssql": sqltypes.TEXT(),
        "oracle": sqld_oracle.CLOB(),
        "starrocks": sqltypes.TEXT(),
        "hana": sqld_oracle.NCLOB(),
        "hive": sqltypes.TEXT(),
    }

    def load_dialect_impl(self, dialect):
        if dialect.name in self._native_dialects:
            return dialect.type_descriptor(self._native_dialects[dialect.name])
        if dialect.name in self._json_dialects:
            return dialect.type_descriptor(self._json_dialects[dialect.name])
        return dialect.type_descriptor(DatabaseJsonType())

    def process_bind_param(self, ukf_value, dialect):
        if ukf_value is None:
            return None
        if dialect.name in self._native_dialects:
            return [float(item) for item in ukf_value]
        serialized = [str(float(item)) for item in ukf_value]
        return DatabaseJsonType().process_bind_param(serialized, dialect)

    def process_result_value(self, db_value, dialect):
        if db_value is None:
            return None
        if dialect.name in self._native_dialects:
            return [float(item) for item in db_value]
        return [float(item) for item in DatabaseJsonType().process_result_value(db_value, dialect)]
