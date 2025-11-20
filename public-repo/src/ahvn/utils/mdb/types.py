"""MongoDB type definitions and conversion utilities for UKF models."""

__all__ = [
    "BaseMongoType",
    "MongoIdType",
    "MongoTextType",
    "MongoIntegerType",
    "MongoBooleanType",
    "MongoDurationType",
    "MongoTimestampType",
    "MongoJsonType",
    "MongoVectorType",
    "MongoTagsType",
    "MongoSynonymsType",
    "MongoRelatedType",
    "MongoAuthsType",
    "MONGO_FIELD_TYPES",
    "MONGO_VIRTUAL_FIELD_TYPES",
]

from ..basic.hash_utils import fmt_hash
from ..basic.serialize_utils import AhvnJsonEncoder, AhvnJsonDecoder, dumps_json, loads_json

import datetime
import calendar
from typing import Any, Optional, List, Dict


class BaseMongoType:
    """Base class for MongoDB field types with UKF conversion."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def from_ukf(self, ukf_value: Any) -> Any:
        """Convert UKF value to MongoDB value."""
        return ukf_value

    def to_ukf(self, mongo_value: Any) -> Any:
        """Convert MongoDB value to UKF value."""
        return mongo_value


class MongoIdType(BaseMongoType):
    """ID type for MongoDB (_id field).

    UKF IDs can be very large integers (beyond 64-bit).
    MongoDB only supports up to 64-bit integers (8 bytes).
    We store IDs as strings to avoid overflow.
    """

    def from_ukf(self, ukf_value: Any) -> Optional[str]:
        """Convert UKF ID to MongoDB _id (string)."""
        return None if ukf_value is None else fmt_hash(ukf_value)

    def to_ukf(self, mongo_value: Any) -> Optional[int]:
        """Convert MongoDB _id to UKF ID (integer)."""
        return None if mongo_value is None else int(mongo_value)


class MongoTextType(BaseMongoType):
    """Text type for MongoDB (string)."""

    def __init__(self, length: Optional[int] = None, **kwargs):
        super().__init__(**kwargs)
        self.length = length

    def from_ukf(self, ukf_value: Any) -> Optional[str]:
        """Convert UKF text to MongoDB string."""
        return None if ukf_value is None else str(ukf_value)

    def to_ukf(self, mongo_value: Any) -> Optional[str]:
        """Convert MongoDB string to UKF text."""
        return None if mongo_value is None else str(mongo_value)


class MongoIntegerType(BaseMongoType):
    """Integer type for MongoDB."""

    def from_ukf(self, ukf_value: Any) -> Optional[int]:
        """Convert UKF integer to MongoDB integer."""
        return None if ukf_value is None else int(ukf_value)

    def to_ukf(self, mongo_value: Any) -> Optional[int]:
        """Convert MongoDB integer to UKF integer."""
        return None if mongo_value is None else int(mongo_value)


class MongoBooleanType(BaseMongoType):
    """Boolean type for MongoDB."""

    def from_ukf(self, ukf_value: Any) -> Optional[bool]:
        """Convert UKF boolean to MongoDB boolean."""
        return None if ukf_value is None else bool(ukf_value)

    def to_ukf(self, mongo_value: Any) -> Optional[bool]:
        """Convert MongoDB boolean to UKF boolean."""
        return None if mongo_value is None else bool(mongo_value)


class MongoDurationType(BaseMongoType):
    """Duration type for MongoDB (stored as integer seconds)."""

    def from_ukf(self, ukf_value: Optional[datetime.timedelta]) -> Optional[int]:
        """Convert UKF timedelta to MongoDB integer (seconds)."""
        return None if ukf_value is None else int(ukf_value.total_seconds())

    def to_ukf(self, mongo_value: Optional[int]) -> Optional[datetime.timedelta]:
        """Convert MongoDB integer (seconds) to UKF timedelta."""
        return None if mongo_value is None else datetime.timedelta(seconds=int(mongo_value))


class MongoTimestampType(BaseMongoType):
    """Timestamp type for MongoDB (stored as integer or datetime)."""

    def from_ukf(self, ukf_value: Optional[datetime.datetime]) -> Optional[int]:
        """Convert UKF datetime to MongoDB integer (Unix timestamp)."""
        return None if ukf_value is None else int(calendar.timegm(ukf_value.utctimetuple()))

    def to_ukf(self, mongo_value: Optional[int]) -> Optional[datetime.datetime]:
        """Convert MongoDB integer (Unix timestamp) to UKF datetime."""
        return None if mongo_value is None else datetime.datetime.fromtimestamp(mongo_value, tz=datetime.timezone.utc)


class MongoJsonType(BaseMongoType):
    """JSON type for MongoDB (stored as embedded document)."""

    def from_ukf(self, ukf_value: Any) -> Optional[Dict[str, Any]]:
        """Convert UKF JSON to MongoDB embedded document."""
        if ukf_value is None:
            return None
        # MongoDB supports native JSON/BSON, so just transform
        return AhvnJsonEncoder.transform(ukf_value)

    def to_ukf(self, mongo_value: Optional[Dict[str, Any]]) -> Any:
        """Convert MongoDB embedded document to UKF JSON."""
        if mongo_value is None:
            return None
        # Reverse transformation
        return AhvnJsonDecoder.transform(mongo_value)


class MongoVectorType(BaseMongoType):
    """Vector type for MongoDB (stored as array of floats)."""

    def from_ukf(self, ukf_value: Optional[List[float]]) -> Optional[List[float]]:
        """Convert UKF vector to MongoDB array."""
        if ukf_value is None:
            return None
        return [float(x) for x in ukf_value]

    def to_ukf(self, mongo_value: Optional[List[float]]) -> Optional[List[float]]:
        """Convert MongoDB array to UKF vector."""
        if mongo_value is None:
            return None
        return [float(x) for x in mongo_value]


class MongoTagsType(BaseMongoType):
    """Tags type for MongoDB (stored as array of {slot, value} subdocuments).

    UKF tags are stored as strings like "[slot:value]".
    MongoDB stores them as subdocuments: [{"slot": "...", "value": "..."}, ...]
    """

    def from_ukf(self, ukf_value: Optional[set]) -> Optional[List[Dict[str, str]]]:
        """Convert UKF tags (set of "[slot:value]" strings) to MongoDB array."""
        if ukf_value is None:
            return None
        result = []
        for tag in sorted(list(ukf_value)):
            tag_str = str(tag)
            # Parse "[slot:value]" format
            if tag_str.startswith("[") and ":" in tag_str and tag_str.endswith("]"):
                tag_str = tag_str[1:-1]  # Remove brackets
                parts = tag_str.split(":", 1)  # Split on first colon only
                if len(parts) == 2:
                    result.append({"slot": parts[0], "value": parts[1]})
                else:
                    # Fallback for malformed tags
                    result.append({"slot": "", "value": tag_str})
            else:
                # Tag without bracket format, store as-is
                result.append({"slot": "", "value": tag_str})
        return result

    def to_ukf(self, mongo_value: Optional[List[Dict[str, str]]]) -> Optional[set]:
        """Convert MongoDB array to UKF tags (set of "[slot:value]" strings)."""
        if mongo_value is None:
            return set()
        result = set()
        for doc in mongo_value:
            slot = doc.get("slot", "")
            value = doc.get("value", "")
            if slot:
                result.add(f"[{slot}:{value}]")
            else:
                result.add(value)
        return result


class MongoSynonymsType(BaseMongoType):
    """Synonyms type for MongoDB (stored as array of strings).

    UKF synonyms are already a set of strings.
    """

    def from_ukf(self, ukf_value: Optional[set]) -> Optional[List[str]]:
        """Convert UKF synonyms (set of strings) to MongoDB array."""
        if ukf_value is None:
            return None
        return [str(s) for s in ukf_value]

    def to_ukf(self, mongo_value: Optional[List[str]]) -> Optional[set]:
        """Convert MongoDB array to UKF synonyms (set of strings)."""
        if mongo_value is None:
            return set()
        return {str(s) for s in mongo_value}


class MongoRelatedType(BaseMongoType):
    """Related type for MongoDB (stored as array of relation subdocuments).

    UKF related are 5-element tuples:
    (subject_id: int, relation: str, object_id: int, relation_id: Optional[int], relation_resources: Optional[str])

    The relation_resources is a JSON string that gets stored in MongoDB as-is.
    """

    def from_ukf(self, ukf_value: Optional[set]) -> Optional[List[Dict[str, Any]]]:
        """Convert UKF related (set of 5-tuples) to MongoDB array."""
        if ukf_value is None:
            return None
        result = []
        for item in ukf_value:
            if len(item) >= 5:
                doc = {
                    "subject_id": fmt_hash(item[0]),
                    "relation": str(item[1]),
                    "object_id": fmt_hash(item[2]),
                    "relation_id": fmt_hash(item[3]) if item[3] is not None else None,
                    # Due to set constraint, UKF actually stores JSON string here, while mongo supports dict
                    "relation_resources": loads_json(item[4]) if item[4] is not None else None,
                }
                result.append(doc)
        return result

    def to_ukf(self, mongo_value: Optional[List[Dict[str, Any]]]) -> Optional[set]:
        """Convert MongoDB array of subdocuments to UKF related (set of 5-tuples)."""
        if mongo_value is None:
            return set()
        result = set()
        for doc in mongo_value:
            result.add(
                (
                    int(doc["subject_id"]),
                    str(doc["relation"]),
                    int(doc["object_id"]),
                    int(doc["relation_id"]) if doc.get("relation_id") is not None else None,
                    # Due to set constraint, UKF actually stores JSON string here, while mongo supports dict
                    dumps_json(doc["relation_resources"], indent=None) if doc.get("relation_resources") is not None else None,
                )
            )
        return result


class MongoAuthsType(BaseMongoType):
    """Authorities type for MongoDB (stored as array of subdocuments).

    UKF stores auths as set of "[user:authority]" strings.
    We parse this into subdocuments with user and authority fields.
    """

    def from_ukf(self, ukf_value: Optional[set]) -> Optional[List[Dict[str, str]]]:
        """Convert UKF auths (set of "[user:authority]" strings) to MongoDB array."""
        if ukf_value is None:
            return None
        result = []
        for auth_str in ukf_value:
            # Parse "[user:authority]" format
            auth_str = str(auth_str).strip()
            if auth_str.startswith("[") and auth_str.endswith("]"):
                auth_str = auth_str[1:-1]

            if ":" in auth_str:
                user, authority = auth_str.split(":", 1)
                result.append({"user": user.strip(), "authority": authority.strip()})
            else:
                # Fallback for invalid format
                result.append({"user": auth_str, "authority": ""})
        return result

    def to_ukf(self, mongo_value: Optional[List[Dict[str, str]]]) -> Optional[set]:
        """Convert MongoDB array to UKF auths (set of "[user:authority]" strings)."""
        if mongo_value is None:
            return set()
        return {f"[{auth['user']}:{auth['authority']}]" for auth in mongo_value}


# MongoDB field type mappings
MONGO_FIELD_TYPES = {
    "id": MongoIdType(),
    "int": MongoIntegerType(),
    "bool": MongoBooleanType(),
    "short_text": MongoTextType(length=255),
    "medium_text": MongoTextType(length=2047),
    "long_text": MongoTextType(length=65535),
    "timestamp": MongoTimestampType(),
    "duration": MongoDurationType(),
    "json": MongoJsonType(),
    "tags": MongoTagsType(),
    "synonyms": MongoSynonymsType(),
    "related": MongoRelatedType(),
    "auths": MongoAuthsType(),
    "vector": MongoVectorType(),
}

# Virtual field type mappings
MONGO_VIRTUAL_FIELD_TYPES = {
    "id": "id",
    "expiration_timestamp": "timestamp",
    "_key": "long_text",
    "_vec": "vector",
}
