"""Vector database type definitions and conversion utilities for UKF models."""

__all__ = [
    "BaseVdbType",
    "VdbIdType",
    "VdbTextType",
    "VdbIntegerType",
    "VdbBooleanType",
    "VdbDurationType",
    "VdbTimestampType",
    "VdbJsonType",
    "VdbVectorType",
    "VdbTagsType",
    "VdbSynonymsType",
    "VdbRelatedType",
    "VdbAuthsType",
]

from ..basic.hash_utils import fmt_hash
from ..basic.serialize_utils import dumps_json, loads_json, AhvnJsonEncoder, AhvnJsonDecoder

import datetime
import calendar

try:
    import pyarrow as pa

    HAS_PYARROW = True
except ImportError:
    pa = None
    HAS_PYARROW = False


class BaseVdbType:
    """Base class for vector database field types with UKF conversion."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def from_ukf(self, ukf_value, backend=None):
        return ukf_value

    def to_ukf(self, vdb_value, backend=None):
        return vdb_value

    def pyarrow_type(self, **kwargs):
        if not HAS_PYARROW:
            return None
        raise NotImplementedError("Subclasses must implement to_pyarrow")


class VdbIdType(BaseVdbType):
    """ID type for vector databases."""

    def from_ukf(self, ukf_value, backend=None):
        return None if ukf_value is None else fmt_hash(ukf_value)

    def to_ukf(self, vdb_value, backend=None):
        return None if vdb_value is None else int(vdb_value)

    def pyarrow_type(self, **kwargs):
        return pa.string() if HAS_PYARROW else None


class VdbTextType(BaseVdbType):
    """Text type for vector databases."""

    def __init__(self, length=None, **kwargs):
        super().__init__(**kwargs)
        self.length = length

    def from_ukf(self, ukf_value, backend=None):
        return None if ukf_value is None else str(ukf_value)

    def to_ukf(self, vdb_value, backend=None):
        return None if vdb_value is None else str(vdb_value)

    def pyarrow_type(self, **kwargs):
        return pa.string() if HAS_PYARROW else None


class VdbIntegerType(BaseVdbType):
    """Integer type for vector databases."""

    def from_ukf(self, ukf_value, backend=None):
        return None if ukf_value is None else int(ukf_value)

    def to_ukf(self, vdb_value, backend=None):
        return None if vdb_value is None else int(vdb_value)

    def pyarrow_type(self, **kwargs):
        return pa.int64() if HAS_PYARROW else None


class VdbBooleanType(BaseVdbType):
    """Boolean type for vector databases."""

    def from_ukf(self, ukf_value, backend=None):
        return None if ukf_value is None else bool(ukf_value)

    def to_ukf(self, vdb_value, backend=None):
        return None if vdb_value is None else bool(vdb_value)

    def pyarrow_type(self, **kwargs):
        return pa.bool_() if HAS_PYARROW else None


class VdbDurationType(BaseVdbType):
    def from_ukf(self, ukf_value, backend=None):
        return None if ukf_value is None else int(ukf_value.total_seconds())

    def to_ukf(self, vdb_value, backend=None):
        return None if vdb_value is None else datetime.timedelta(seconds=int(vdb_value))

    def pyarrow_type(self, **kwargs):
        return pa.string() if HAS_PYARROW else None


class VdbTimestampType(BaseVdbType):
    def from_ukf(self, ukf_value, backend=None):
        return None if ukf_value is None else int(calendar.timegm(ukf_value.utctimetuple()))

    def to_ukf(self, vdb_value, backend=None):
        return None if vdb_value is None else datetime.datetime.fromtimestamp(vdb_value, tz=datetime.timezone.utc)

    def pyarrow_type(self, **kwargs):
        return pa.timestamp("us", tz="UTC") if HAS_PYARROW else None


class VdbJsonType(BaseVdbType):
    """JSON type with backend-aware serialization."""

    # Backends that support native JSON types
    _native_backends = {"milvuslite"}

    # Backends that require string serialization
    _string_backends = {"lancedb", "chroma"}

    def from_ukf(self, ukf_value, backend=None):
        if ukf_value is None:
            return None
        if backend in self._native_backends:
            return AhvnJsonEncoder.transform(ukf_value)
        if backend in self._string_backends:
            return dumps_json(AhvnJsonEncoder.transform(ukf_value), indent=None)
        return dumps_json(AhvnJsonEncoder.transform(ukf_value), indent=None)

    def to_ukf(self, vdb_value, backend=None):
        if vdb_value is None:
            return None
        if backend in self._native_backends:
            return AhvnJsonDecoder.transform(vdb_value)
        if backend in self._string_backends:
            return loads_json(AhvnJsonDecoder.transform(vdb_value))
        return loads_json(AhvnJsonDecoder.transform(vdb_value))

    def pyarrow_type(self, **kwargs):
        return pa.string() if HAS_PYARROW else None


class VdbVectorType(BaseVdbType):
    """Vector/embedding type for vector databases."""

    def __init__(self, dimension=None, **kwargs):
        super().__init__(**kwargs)
        self.dimension = dimension

    def from_ukf(self, ukf_value, backend=None):
        return None if ukf_value is None else [float(x) for x in ukf_value]

    def to_ukf(self, vdb_value, backend=None):
        return None if vdb_value is None else [float(x) for x in vdb_value]

    def pyarrow_type(self, dim: int = 768, **kwargs):
        return pa.list_(pa.float32(), dim) if HAS_PYARROW else None


class VdbTagsType(BaseVdbType):
    """Tags type with backend-aware serialization."""

    # Backends that support native array types
    _native_backends = {"milvuslite"}

    # Backends that require string serialization
    _string_backends = {"lancedb", "chroma"}

    def from_ukf(self, ukf_value, backend=None):
        if ukf_value is None:
            return None
        tags_list = sorted(list(ukf_value))
        if backend in self._native_backends:
            return tags_list
        if backend in self._string_backends:
            return "\n".join(tags_list)
        return "\n".join(tags_list)

    def to_ukf(self, vdb_value, backend=None):
        if vdb_value is None:
            return set()
        if backend in self._native_backends:
            return set(vdb_value)
        if backend in self._string_backends:
            return set(vdb_value.split("\n")) if vdb_value else set()
        return set(vdb_value.split("\n")) if vdb_value else set()

    def pyarrow_type(self, **kwargs):
        return pa.string() if HAS_PYARROW else None


class VdbSynonymsType(BaseVdbType):
    """Synonyms type with backend-aware serialization."""

    # Backends that support native array types
    _native_backends = {"milvuslite"}

    # Backends that require string serialization
    _string_backends = {"lancedb", "chroma"}

    def from_ukf(self, ukf_value, backend=None):
        if ukf_value is None:
            return None
        synonyms_list = sorted(list(ukf_value))
        if backend in self._native_backends:
            return synonyms_list
        if backend in self._string_backends:
            return "\n".join(synonyms_list)
        return "\n".join(synonyms_list)

    def to_ukf(self, vdb_value, backend=None):
        if vdb_value is None:
            return set()
        if backend in self._native_backends:
            return set(vdb_value)
        if backend in self._string_backends:
            return set(vdb_value.split("\n")) if vdb_value else set()
        return set(vdb_value.split("\n")) if vdb_value else set()

    def pyarrow_type(self, **kwargs):
        return pa.string() if HAS_PYARROW else None


class VdbRelatedType(BaseVdbType):
    """Related type with backend-aware serialization."""

    # Backends that support native array types
    _native_backends = {"milvuslite"}

    # Backends that require string serialization
    _string_backends = {"lancedb", "chroma"}

    def from_ukf(self, ukf_value, backend=None):
        if ukf_value is None:
            return None
        related_list = sorted([list(rel_attr) for rel_attr in ukf_value])
        if backend in self._native_backends:
            return related_list
        if backend in self._string_backends:
            return dumps_json(related_list, indent=None)
        return dumps_json(related_list, indent=None)

    def to_ukf(self, vdb_value, backend=None):
        if vdb_value is None:
            return set()
        if backend in self._native_backends:
            return set(tuple(rel_attr) for rel_attr in vdb_value)
        if backend in self._string_backends:
            parsed_value = loads_json(vdb_value) if vdb_value else []
            return set(tuple(rel_attr) for rel_attr in parsed_value)
        parsed_value = loads_json(vdb_value) if vdb_value else []
        return set(tuple(rel_attr) for rel_attr in parsed_value)

    def pyarrow_type(self, **kwargs):
        return pa.string() if HAS_PYARROW else None


class VdbAuthsType(BaseVdbType):
    """Auths type with backend-aware serialization."""

    # Backends that support native array types
    _native_backends = {"milvuslite"}

    # Backends that require string serialization
    _string_backends = {"lancedb", "chroma"}

    def from_ukf(self, ukf_value, backend=None):
        if ukf_value is None:
            return None
        auths_list = sorted(list(ukf_value))
        if backend in self._native_backends:
            return auths_list
        if backend in self._string_backends:
            return "\n".join(auths_list)
        return "\n".join(auths_list)

    def to_ukf(self, vdb_value, backend=None):
        if vdb_value is None:
            return set()
        if backend in self._native_backends:
            return set(vdb_value)
        if backend in self._string_backends:
            return set(vdb_value.split("\n")) if vdb_value else set()
        return set(vdb_value.split("\n")) if vdb_value else set()

    def pyarrow_type(self, **kwargs):
        return pa.string() if HAS_PYARROW else None
