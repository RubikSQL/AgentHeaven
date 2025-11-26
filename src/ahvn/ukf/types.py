"""Custom Pydantic field types for UKF schema compatibility.

This module provides custom Pydantic field types that handle validation,
serialization, and database mapping for the Universal Knowledge Framework.
These types enable BaseUKF to serve as a single source of truth for schema
definitions across different storage backends.
"""

__all__ = [
    "UKF_TYPES",
    "UKFIdType",
    "UKFIntegerType",
    "UKFBooleanType",
    "UKFShortTextType",
    "UKFMediumTextType",
    "UKFLongTextType",
    "UKFTimestampType",
    "UKFDurationType",
    "UKFJsonType",
    "UKFTagsType",
    "UKFAuthsType",
    "UKFSynonymsType",
    "UKFRelatedType",
    "UKFVectorType",
]

from typing import Dict, Tuple, Optional, Union, List, Iterable
from pydantic_core import PydanticCustomError, core_schema
from ..utils.basic.serialize_utils import loads_json, dumps_json
from ..utils.basic.config_utils import HEAVEN_CM
from .ukf_utils import valid_tag
import numpy as np
import datetime
import isodate
import math


def _get_text_lengths():
    return {"id": 63, "short": 255, "medium": 2047, "long": 65535} | HEAVEN_CM.get("ukf.text", {})


_TEXT_LENGTHS = _get_text_lengths()

UKF_TYPES = dict()


def _ukf_type(cls):
    UKF_TYPES[cls.name] = cls
    return cls


@_ukf_type
class UKFIdType(int):
    """Custom type for UKF ID fields with validation and formatting.

    Validates and converts values to integer IDs, supporting both raw integers
    and formatted hash strings with underscores or dashes.

    It is recommended to use integer IDs generated from `md5hash` in hash_utils.

    Args:
        value: Integer or string representation of an ID.

    Returns:
        int: Validated integer ID.

    Raises:
        PydanticCustomError: If value cannot be converted to a valid integer ID.

    Examples:
        >>> UKFIdType._validate(123)
        123
        >>> UKFIdType._validate("000123")
        123
    """

    name = "id"

    @classmethod
    def __get_pydantic_core_schema__(cls, source, handler):
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.int_schema(),
        )

    @classmethod
    def _validate(cls, value: Union[int, str]) -> int:
        return None if value is None else int(value)


@_ukf_type
class UKFIntegerType(int):
    """Custom type for integer fields with validation.

    Validates and converts values to integers, providing consistent
    handling of numeric inputs including integers, floats and string representations.

    Args:
        value: Integer, float, or string representation of an integer.

    Returns:
        int: Validated integer value.

    Raises:
        PydanticCustomError: If value cannot be converted to a valid integer.

    Examples:
        >>> UKFIntegerType._validate(123)
        123
        >>> UKFIntegerType._validate(123.0)
        123
        >>> UKFIntegerType._validate("123")
        123
    """

    name = "int"

    @classmethod
    def __get_pydantic_core_schema__(cls, source, handler):
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.int_schema(),
        )

    @classmethod
    def _validate(cls, value: Optional[Union[int, float, str]]) -> Optional[int]:
        return None if (value is None) or (math.isnan(value)) else int(str(value))


@_ukf_type
class UKFBooleanType:
    """Custom type for boolean fields with validation.

    Validates and converts various representations to boolean values,
    supporting common string representations and numeric values.

    Args:
        value: Boolean, integer, string, or other value to convert.

    Returns:
        bool: Validated boolean value.

    Raises:
        PydanticCustomError: If value cannot be converted to a valid boolean.

    Examples:
        >>> UKFBooleanType._validate(True)
        True
        >>> UKFBooleanType._validate("true")
        True
        >>> UKFBooleanType._validate(1)
        True
        >>> UKFBooleanType._validate("false")
        False
        >>> UKFBooleanType._validate(0)
        False
    """

    name = "bool"

    @classmethod
    def __get_pydantic_core_schema__(cls, source, handler):
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.bool_schema(),
        )

    @classmethod
    def _validate(cls, value: Optional[Union[bool, int, str]]) -> Optional[bool]:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return bool(value)
        if isinstance(value, str):
            lower_value = value.lower().strip()
            if lower_value in ("true", "1", "yes", "on", "enabled"):
                return True
            elif lower_value in ("false", "0", "no", "off", "disabled"):
                return False
            else:
                raise PydanticCustomError("boolean_format", "Invalid boolean format: {value}", {"value": value})
        return bool(value)


@_ukf_type
class UKFShortTextType(str):
    """Custom type for short text fields with length validation.

    Validates string length against configurable short text limit from config.yaml.
    Default limit is 255 characters (equivalent to SQL VARCHAR(255)).

    Args:
        value: String value to validate.

    Returns:
        str: Validated string value.

    Raises:
        PydanticCustomError: If string exceeds maximum length limit.

    Examples:
        >>> UKFShortTextType._validate("Hello world")
        'Hello world'
        >>> UKFShortTextType._validate("a" * 256)  # Assuming 255 char limit
        PydanticCustomError: short_text_too_long
    """

    name = "short_text"

    @classmethod
    def __get_pydantic_core_schema__(cls, source, handler):
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.str_schema(max_length=_TEXT_LENGTHS.get("short", 255)),
        )

    @classmethod
    def _validate(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        max_length = _TEXT_LENGTHS.get("short", 255)
        if len(value) > max_length:
            raise PydanticCustomError(
                "short_text_too_long",
                "Short text must be {max_length} characters or less, got {length}",
                {"max_length": max_length, "length": len(value)},
            )
        return str(value)

    @classmethod
    def max_length(cls) -> int:
        return _TEXT_LENGTHS.get("short", 255)


@_ukf_type
class UKFMediumTextType(str):
    """Custom type for medium text fields with length validation.

    Validates string length against configurable medium text limit from config.yaml.
    Default limit is 2047 characters (equivalent to SQL VARCHAR(2047)).

    Args:
        value: String value to validate.

    Returns:
        str: Validated string value.

    Raises:
        PydanticCustomError: If string exceeds maximum length limit.

    Examples:
        >>> UKFMediumTextType._validate("Medium length text")
        'Medium length text'
        >>> UKFMediumTextType._validate("a" * 2048)  # Assuming 2047 char limit
        PydanticCustomError: medium_text_too_long
    """

    name = "medium_text"

    @classmethod
    def __get_pydantic_core_schema__(cls, source, handler):
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.str_schema(max_length=_TEXT_LENGTHS.get("medium", 2047)),
        )

    @classmethod
    def _validate(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        max_length = _TEXT_LENGTHS.get("medium", 2047)
        if len(value) > max_length:
            raise PydanticCustomError(
                "medium_text_too_long",
                "Medium text must be {max_length} characters or less, got {length}",
                {"max_length": max_length, "length": len(value)},
            )
        return str(value)

    @classmethod
    def max_length(cls) -> int:
        return _TEXT_LENGTHS.get("medium", 2047)


@_ukf_type
class UKFLongTextType(str):
    """Custom type for long text fields with length validation.

    Validates string length against configurable long text limit from config.yaml.
    Default limit is 65535 characters (equivalent to SQL VARCHAR(65535)).

    Args:
        value: String value to validate.

    Returns:
        str: Validated string value.

    Raises:
        PydanticCustomError: If string exceeds maximum length limit.

    Examples:
        >>> UKFLongTextType._validate("Very long text content")
        'Very long text content'
        >>> UKFLongTextType._validate("a" * 65536)  # Assuming 65535 char limit
        PydanticCustomError: long_text_too_long
    """

    name = "long_text"

    @classmethod
    def __get_pydantic_core_schema__(cls, source, handler):
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.str_schema(max_length=_TEXT_LENGTHS.get("long", 65535)),
        )

    @classmethod
    def _validate(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        max_length = _TEXT_LENGTHS.get("long", 65535)
        if len(value) > max_length:
            raise PydanticCustomError(
                "long_text_too_long",
                "Long text must be {max_length} characters or less, got {length}",
                {"max_length": max_length, "length": len(value)},
            )
        return str(value)

    @classmethod
    def max_length(cls) -> int:
        return _TEXT_LENGTHS.get("long", 65535)


@_ukf_type
class UKFTimestampType(datetime.datetime):
    """Custom type for datetime fields with UTC conversion and validation.

    Validates and normalizes datetime values to UTC timezone with microseconds
    stripped for consistency. Supports various input formats including ISO strings,
    timestamps, and datetime objects.

    Args:
        value: Datetime, ISO string, timestamp (int/float), or datetime object.

    Returns:
        datetime.datetime: UTC datetime with microseconds stripped.

    Raises:
        PydanticCustomError: If value cannot be converted to a valid datetime.

    Examples:
        >>> UKFTimestampType._validate("2023-01-01T12:00:00Z")
        datetime.datetime(2023, 1, 1, 12, 0, tzinfo=datetime.timezone.utc)
        >>> UKFTimestampType._validate(1672574400)  # Unix timestamp
        datetime.datetime(2023, 1, 1, 12, 0, tzinfo=datetime.timezone.utc)
    """

    name = "timestamp"

    @classmethod
    def __get_pydantic_core_schema__(cls, source, handler):
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.datetime_schema(),
        )

    @classmethod
    def _validate(cls, value: Optional[Union[datetime.datetime, str, int, float]]) -> Optional[datetime.datetime]:
        if value is None:
            return None
        if isinstance(value, datetime.datetime):
            dt = value
        elif isinstance(value, (int, float)):
            dt = datetime.datetime.fromtimestamp(value, tz=datetime.timezone.utc)
        elif isinstance(value, str):
            try:
                dt = datetime.datetime.fromisoformat(value)
            except Exception as e:
                raise PydanticCustomError("timestamp_format", "Invalid timestamp format: {value}. Error: {e}", {"value": value, "e": e})
        else:
            raise PydanticCustomError("timestamp_format", "Invalid timestamp format: {value}", {"value": value})
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        else:
            dt = dt.astimezone(datetime.timezone.utc)
        return dt.replace(microsecond=0)


@_ukf_type
class UKFDurationType(datetime.timedelta):
    """Custom type for duration fields with validation.

    Validates and converts various representations to timedelta objects,
    supporting ISO 8601 duration strings and numeric seconds.

    Args:
        value: Timedelta, ISO 8601 duration string, or numeric seconds.

    Returns:
        datetime.timedelta: Validated timedelta object.

    Raises:
        PydanticCustomError: If value cannot be converted to a valid timedelta.

    Examples:
        >>> UKFDurationType._validate("P1DT2H")  # 1 day, 2 hours
        datetime.timedelta(days=1, hours=2)
        >>> UKFDurationType._validate(3600)  # 1 hour in seconds
        datetime.timedelta(seconds=3600)
    """

    name = "duration"

    @classmethod
    def __get_pydantic_core_schema__(cls, source, handler):
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.timedelta_schema(),
        )

    @classmethod
    def _validate(cls, value: Optional[Union[datetime.timedelta, str, int, float]]) -> Optional[datetime.timedelta]:
        if value is None:
            return None
        if isinstance(value, datetime.timedelta):
            return value
        if isinstance(value, (int, float)):
            return datetime.timedelta(seconds=value)
        if isinstance(value, str):
            try:
                return isodate.parse_duration(value)
            except Exception as e:
                raise PydanticCustomError("duration_format", "Invalid duration format: {value}. Error: {e}", {"value": value, "e": e})
        raise PydanticCustomError("duration_format", "Invalid duration format: {value}", {"value": value})


@_ukf_type
class UKFJsonType(dict):
    """Custom type for JSON fields with validation and parsing.

    Validates and converts JSON data, supporting both dictionary objects and
    JSON string representations. Uses custom JSON parser for consistency.

    Args:
        value: Dictionary object or JSON string to validate.

    Returns:
        dict: Validated dictionary object.

    Raises:
        PydanticCustomError: If JSON string cannot be parsed or value is invalid.

    Examples:
        >>> UKFJsonType._validate({"key": "value"})
        {'key': 'value'}
        >>> UKFJsonType._validate('{"key": "value"}')
        {'key': 'value'}
        >>> UKFJsonType._validate(None)
        {}
    """

    name = "json"

    @classmethod
    def __get_pydantic_core_schema__(cls, source, handler):
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.dict_schema(),
        )

    @classmethod
    def _validate(cls, value: Optional[Union[Dict, str]]) -> dict:
        if isinstance(value, str):
            value = loads_json(value)
        return dict() if value is None else dict(value)


@_ukf_type
class UKFTagsType(set):
    """Custom type for tags set with validation and serialization.

    Validates and converts various iterable types to a set of string tags.
    Handles None values gracefully by returning empty set. Also supports
    auth tuples which are converted to "[user:authority]" tag format.

    Args:
        value: Set, list, tuple, or other iterable of tag values. Can also
            include auth tuples (user, authority) which are converted to tags.

    Returns:
        set: Set of string tags.

    Raises:
        TypeError: If value cannot be iterated over.

    Examples:
        >>> UKFTagsType._validate(["tag1", "tag2"])
        {'tag1', 'tag2'}
        >>> UKFTagsType._validate({"tag1", "tag2"})
        {'tag1', 'tag2'}
        >>> UKFTagsType._validate([("user1", "read")])  # Auth tuple as tag
        {'[user1:read]'}
        >>> UKFTagsType._validate(None)
        set()
    """

    name = "tags"

    @classmethod
    def __get_pydantic_core_schema__(cls, source, handler):
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.set_schema(core_schema.str_schema()),
        )

    @classmethod
    def _validate(cls, value: Optional[Iterable[Union[Tuple[str, str], List[str], str]]]) -> set:
        if value is None:
            return set()
        s = set()
        for item in value:
            if isinstance(item, (tuple, list)) and len(item) == 2:
                s.add(f"[{item[0]}:{item[1]}]")
            elif isinstance(item, str):
                s.add(valid_tag(item))
        return s


@_ukf_type
class UKFAuthsType(UKFTagsType):
    name = "auths"

    @classmethod
    def __get_pydantic_core_schema__(cls, source, handler):
        return super().__get_pydantic_core_schema__(source, handler)

    @classmethod
    def _validate(cls, value: Optional[Iterable[Union[Tuple[str, str], List[str], str]]]) -> set:
        return super()._validate(value)


@_ukf_type
class UKFSynonymsType(set):
    """Custom type for synonyms set with validation.

    Validates and converts various iterable types to a set of string synonyms.
    Similar to UKFTagsType but specifically for synonym collections.

    Args:
        value: Set, list, tuple, or other iterable of synonym values.

    Returns:
        set: Set of string synonyms.

    Raises:
        TypeError: If value cannot be iterated over.

    Examples:
        >>> UKFSynonymsType._validate(["synonym1", "synonym2"])
        {'synonym1', 'synonym2'}
        >>> UKFSynonymsType._validate(None)
        set()
    """

    name = "synonyms"

    @classmethod
    def __get_pydantic_core_schema__(cls, source, handler):
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.set_schema(core_schema.str_schema()),
        )

    @classmethod
    def _validate(cls, value: Union[set, list, tuple]) -> set:
        if value is None:
            return set()
        return set(str(item).strip() for item in value if item is not None)


@_ukf_type
class UKFRelatedType(set):
    """Custom type for related tuples set with complex validation.

    Validates and converts relation tuples with 3-5 elements representing
    subject-relation-object triples with optional relation_id and relation_resources.
    Uses UKFIdType validation for all ID fields, supporting both raw integers
    and formatted hash strings.

    Args:
        value: Set, list, or tuple of relation tuples with format:
            (subject_id, relation, object_id, [relation_id], [relation_resources])

    Returns:
        set: Set of 5-element relation tuples with normalized types.

    Raises:
        PydanticCustomError: If any tuple has fewer than 3 elements or invalid ID format.

    Examples:
        >>> UKFRelatedType._validate([(1, "knows", 2)])
        {(1, 'knows', 2, None, None)}
        >>> UKFRelatedType._validate([(1.0, "works_at", 3.0, 4, '{"since": "2020"}')])
        {(1, 'works_at', 3, 4, '{"since": "2020"}')}
        >>> UKFRelatedType._validate([("123-456", "relates_to", "789_012")])
        {(123456, 'relates_to', 789012, None, None)}
    """

    name = "related"

    @classmethod
    def __get_pydantic_core_schema__(cls, source, handler):
        tuple_schema = core_schema.tuple_schema(
            [
                core_schema.int_schema(),  # subject_id: int or str
                core_schema.str_schema(),  # relation: str
                core_schema.int_schema(),  # object_id: int or str
                core_schema.nullable_schema(core_schema.int_schema()),  # relation_id: optional int or str
                core_schema.nullable_schema(core_schema.str_schema()),  # relation_resources: optional json serialized dict
            ]
        )
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.set_schema(tuple_schema),
        )

    @classmethod
    def _validate(cls, value: Optional[Iterable[Tuple[int, str, int, Optional[int], Optional[Dict]]]]) -> set:
        """Validate and convert to set of relation tuples."""
        if value is None:
            return set()
        s = set()
        for item in value:
            if len(item) < 3:
                raise PydanticCustomError(
                    "relation_tuple_format",
                    "Relation tuple must have at least 3 elements: (subject_id, relation, object_id). Got {item}.",
                    {"item": item},
                )
            subject_id = UKFIdType._validate(item[0])
            relation = UKFShortTextType._validate(item[1])
            object_id = UKFIdType._validate(item[2])
            relation_id = None if (len(item) <= 3) or (item[3] is None) else UKFIdType._validate(item[3])
            relation_resources = None if (len(item) <= 4) or (item[4] is None) else dumps_json(UKFJsonType._validate(item[4]), indent=None)
            # Since Sets does not support Dict as element, we convert relation_resources to JSON string
            s.add((subject_id, relation, object_id, relation_id, relation_resources))
        return s


@_ukf_type
class UKFVectorType(list):
    """Custom type for vector fields with validation and serialization.

    Validates and converts various iterable types to a list of floats.
    Handles None values gracefully by returning empty list.

    Args:
        value: List, tuple, or other iterable of numeric values.

    Returns:
        list: List of floats representing the vector.

    Raises:
        TypeError: If value cannot be iterated over or contains non-numeric values.

    Examples:
        >>> UKFVectorType._validate([1, 2, 3])
        [1.0, 2.0, 3.0]
        >>> UKFVectorType._validate((4.5, 5.5))
        [4.5, 5.5]
        >>> UKFVectorType._validate(None)
        []
    """

    name = "vector"

    @classmethod
    def __get_pydantic_core_schema__(cls, source, handler):
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.list_schema(core_schema.float_schema()),
        )

    @classmethod
    def _validate(cls, value: Optional[Iterable[Union[int, float]]]) -> Optional[List[float]]:
        if value is None:
            return None
        if isinstance(value, np.ndarray):
            return value.tolist()
        return [float(item) for item in value]
