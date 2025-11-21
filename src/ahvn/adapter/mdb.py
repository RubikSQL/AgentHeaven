"""\
MongoDB adapter for converting between UKF objects and MongoDB documents.
"""

__all__ = [
    "MongoUKFAdapter",
]

from .base import BaseUKFAdapter

from ..utils.mdb.types import MONGO_FIELD_TYPES, MONGO_VIRTUAL_FIELD_TYPES
from ..ukf.base import BaseUKF
from ..utils.basic.log_utils import get_logger

from typing import Any, Dict, List, Optional

logger = get_logger(__name__)


class MongoUKFAdapter(BaseUKFAdapter):
    """\
    MongoDB adapter for converting between UKF objects and MongoDB documents.

    Uses type-based field mapping system (like ORMUKFAdapter and VdbUKFAdapter):
    - Dynamically maps UKF fields based on BaseUKF.schema()
    - Uses MONGO_FIELD_TYPES for type conversion
    - Handles virtual fields (_key, _vec)
    - Supports multi-valued fields as embedded arrays

    Example:
        ```python
        adapter = MongoUKFAdapter(name="test_adapter")

        # Convert UKF to MongoDB document
        ukf = BaseUKF(id=1, name="test", type="test_type")
        doc = adapter.from_ukf(ukf)
        # doc = {"_id": 1, "name": "test", "type": "test_type", ...}

        # Convert MongoDB document back to UKF
        data = adapter.to_ukf_data(doc)
        ukf_restored = BaseUKF.from_dict(data, polymorphic=True)
        ```
    """

    virtual_fields = tuple(k for k in MONGO_VIRTUAL_FIELD_TYPES.keys() if k not in {"_key", "_vec"})

    indices = [
        [("type", 1), ("name", 1), ("version", 1), ("variant", 1)],
        [("type", 1), ("workspace", 1), ("collection", 1)],
        [("type", 1), ("timestamp", -1)],
        [("creator", 1), ("owner", 1)],
        [("expiration_timestamp", 1)],
        [("tags.slot", 1), ("tags.value", 1)],
        [("auths.user_id", 1), ("auths.authority", 1)],
        [("synonyms", 1)],
        [("related.relation", 1)],
    ]

    def __init__(
        self,
        name: str,
        include: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        **kwargs,
    ):
        """\
        Initialize adapter with field selection.

        Args:
            name: Adapter name
            include: Fields to include (if None, includes all BaseUKF fields)
            exclude: Fields to exclude
            **kwargs: Additional parameters (reserved for future use)
        """
        super().__init__(name=name, include=include, exclude=exclude)
        self.key_field = f"_{self.name}_key"
        self.embedding_field = f"_{self.name}_vec"
        self.embedding_idx = f"_{self.name}_vec_idx"

    def parse_id(self, key: int):
        return MONGO_FIELD_TYPES["id"].from_ukf(int(key))

    def create_indices(self, mdb):
        for idx_spec in self.indices:
            try:
                if not all(key in self.fields for key, _ in idx_spec):
                    continue
                name = f"idx_{'_'.join([k[0].replace('.', '_') for k in idx_spec])}"
                mdb.create_index(idx_spec, name=name)
            except Exception as e:
                logger.warning(f"Index creation failed: {e}")

    def create_vector_index(self, mdb, dim):
        return mdb.create_vector_index(
            embedding_idx=self.embedding_idx,
            embedding_field=self.embedding_field,
            dim=dim,
        )

    def from_ukf(self, kl: BaseUKF, key: Optional[str] = None, embedding: Optional[List[float]] = None) -> Dict[str, Any]:
        """\
        Convert BaseUKF to MongoDB document using type-based mapping.

        Iterates through self.fields and uses MONGO_FIELD_TYPES for conversion:
        - For each field in self.fields:
            - Get field type from BaseUKF.schema()
            - Get corresponding MongoFieldType from MONGO_FIELD_TYPES
            - Call field_type.from_ukf(ukf_value) to convert
        - Handle virtual fields separately (_key, _vec)

        Args:
            kl: BaseUKF object to convert
            key: Optional key for vector search (stored as _key)
            embedding: Optional embedding vector (stored as _vec)

        Returns:
            Dict with structure:
            {
                "_id": <int>,
                "name": "...",
                "type": "...",
                "tags": [{"slot": "...", "value": "..."}, ...],
                "auths": [{"user_id": "...", "authority": "..."}, ...],
                "synonyms": ["...", "..."],
                "related": [{...}, ...],
                "_key": "...",
                "_vec": [...],
                ...other fields based on include/exclude...
            }
        """
        document = {}
        ukf_schema = BaseUKF.schema()
        for field_name in self.fields:
            if field_name in self.virtual_fields:
                continue
            ukf_field_type = ukf_schema.get(field_name)
            if ukf_field_type is None:
                continue
            field_type = MONGO_FIELD_TYPES.get(ukf_field_type.name)
            if field_type:
                ukf_value = getattr(kl, field_name)
                document[field_name] = field_type.from_ukf(ukf_value)
        # Handle virtual fields
        document["_id"] = MONGO_FIELD_TYPES["id"].from_ukf(kl.id)
        document["expiration_timestamp"] = MONGO_FIELD_TYPES["timestamp"].from_ukf(kl.expiration_timestamp)
        document[self.key_field] = kl.name if key is None else key
        document[self.embedding_field] = None if embedding is None else MONGO_FIELD_TYPES["vector"].from_ukf(embedding)

        return document

    def to_ukf_data(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """\
        Convert MongoDB document to UKF initialization dict using type-based mapping.

        Iterates through self.fields and uses MONGO_FIELD_TYPES for conversion:
        - For each field in self.fields:
            - Get field type from BaseUKF.schema()
            - Get corresponding MongoFieldType from MONGO_FIELD_TYPES
            - Call field_type.to_ukf(mongo_value) to convert

        Args:
            document: MongoDB document to convert

        Returns:
            Dict suitable for BaseUKF initialization
        """
        data = {}
        ukf_schema = BaseUKF.schema()

        for field_name in self.fields:
            if field_name in self.virtual_fields:
                continue
            ukf_field_type = ukf_schema.get(field_name)
            if ukf_field_type is None:
                continue
            field_type = MONGO_FIELD_TYPES.get(ukf_field_type.name)
            if field_type:
                mongo_value = document.get(field_name)
                data[field_name] = field_type.to_ukf(mongo_value)
        return data

    def from_result(self, result: Any) -> Any:
        """\
        Convert a query result from MongoDB to the appropriate representation.

        Args:
            result: The raw result from a MongoDB query

        Returns:
            The converted representation (currently returns as-is)
        """
        # For future extensions if needed
        return result
