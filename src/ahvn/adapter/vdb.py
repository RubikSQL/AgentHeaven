from __future__ import annotations

__all__ = [
    "VdbUKFAdapter",
]

from .base import BaseUKFAdapter

from ..utils.vdb.types import *
from ..utils.basic.config_utils import HEAVEN_CM

from ..ukf.base import BaseUKF
from ..utils.deps import deps

from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from llama_index.core.schema import TextNode


def get_text_node():
    return deps.load("llama_index.core.schema").TextNode


VDB_FIELD_TYPES = {
    "id": VdbIdType(),
    "int": VdbIntegerType(),
    "bool": VdbBooleanType(),
    "short_text": VdbTextType(length=HEAVEN_CM.get("ukf.text.short", 255)),
    "medium_text": VdbTextType(length=HEAVEN_CM.get("ukf.text.medium", 2047)),
    "long_text": VdbTextType(length=HEAVEN_CM.get("ukf.text.long", 65535)),
    "timestamp": VdbTimestampType(),
    "duration": VdbDurationType(),
    "json": VdbJsonType(),
    "tags": VdbTagsType(),
    "synonyms": VdbSynonymsType(),
    "related": VdbRelatedType(),
    "auths": VdbAuthsType(),
    "vector": VdbVectorType(),
}
VDB_VIRTUAL_FIELD_TYPES = {
    "id": "id",
    "expiration_timestamp": "timestamp",
    "_key": "long_text",
    "_vec": "vector",
}


class VdbUKFAdapter(BaseUKFAdapter):
    """\
    Vector database adapter that provides logical conversion between UKF objects and vector database records.

    This adapter creates field type mappings dynamically based on the included fields
    and provides conversion methods between UKF objects and LlamaIndex TextNode objects.
    Does not handle any physical connection operations - those are managed by VectorDatabase.
    """

    virtual_fields = tuple(k for k in VDB_VIRTUAL_FIELD_TYPES.keys() if k not in set(["_key", "_vec"]))

    def __init__(
        self,
        backend=None,
        *args,
        **kwargs,
    ):
        """\
        Initialize the vector adapter with specified field inclusion.

        Args:
            name: Name of the adapter instance.
            include: List of BaseUKF field names to include in the vector database schema.
                If None, includes all available BaseUKF fields plus virtual fields.
                The 'id' field is always included automatically.
            exclude: List of BaseUKF field names to exclude from the vector database schema.
                If None, excludes no fields.
            backend: Vector database backend ('lancedb', 'chroma', 'milvuslite', etc.).
                Used for backend-aware type conversions.
            *args: Additional positional arguments.
            **kwargs: Additional configuration parameters.

        Returns:
            None
        """
        super().__init__(*args, **kwargs)
        self.key_field = "_key"
        self.embedding_field = "_vec"
        self.backend = backend

    def parse_id(self, key: int):
        return VDB_FIELD_TYPES["id"].from_ukf(int(key), backend=self.backend)

    def from_ukf(self, kl: BaseUKF, key: Optional[str] = None, embedding: Optional[List[float]] = None) -> "TextNode":
        """\
        Convert a BaseUKF object to a LlamaIndex TextNode.

        Args:
            kl: BaseUKF object to convert.
            key: Optional text content for the TextNode. If None, uses kl.name.
            embedding: Optional vector embedding for the TextNode. If None, no embedding is set.

        Returns:
            LlamaIndex TextNode object representing the UKF data.
        """
        data = {}
        ukf_schema = BaseUKF.schema()
        for field_name in self.fields:
            if field_name in self.virtual_fields:
                continue
            ukf_field_type = ukf_schema.get(field_name)
            if ukf_field_type is None:
                continue
            field_type = VDB_FIELD_TYPES.get(ukf_field_type.name)
            if field_type:
                ukf_value = getattr(kl, field_name)
                data[field_name] = field_type.from_ukf(ukf_value, backend=self.backend)
        # Ad-hoc on the virtual_fields
        data["id"] = VDB_FIELD_TYPES["id"].from_ukf(kl.id, backend=self.backend)
        data["expiration_timestamp"] = VDB_FIELD_TYPES["timestamp"].from_ukf(kl.expiration_timestamp, backend=self.backend)
        data[self.key_field] = kl.name if key is None else key
        vector = VDB_FIELD_TYPES["vector"].from_ukf(embedding, backend=self.backend)
        return get_text_node()(text=data[self.key_field], embedding=vector, metadata=data, id_=data["id"])

    def to_ukf_data(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        """\
        Convert a vector database entity to a dictionary suitable for BaseUKF initialization.

        Args:
            entity: Dictionary representing the vector database entity.

        Returns:
            A dictionary of field names and values for BaseUKF initialization.
        """
        data = {}
        ukf_schema = BaseUKF.schema()

        for field_name in self.fields:
            if field_name in self.virtual_fields:
                continue
            ukf_field_type = ukf_schema.get(field_name)
            if ukf_field_type is None:
                continue
            field_type = VDB_FIELD_TYPES.get(ukf_field_type.name)
            if field_type:
                vdb_value = entity.metadata.get(field_name)
                data[field_name] = field_type.to_ukf(vdb_value, backend=self.backend)
        return data

    def from_result(self, result: Any) -> Any:
        """\
        Convert a query result from the vector database to the appropriate representation.

        Args:
            result: The raw result from a vector database query.

        Returns:
            The converted representation.
        """
        # Empty implementation - to be extended for future VectorStoreQuery inputs
        pass
