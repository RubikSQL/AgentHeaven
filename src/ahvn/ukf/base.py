"""Universal Knowledge Framework (UKF) base module.

This module provides the core :class:`BaseUKF` model and a small set of
utility functions used throughout the UKF implementation:

- Tag helpers: parsing, grouping and membership checks (``tag_s``, ``tag_v``, ``tag_t``, ``ptags``, ``gtags``, ``has_tag``)
- Relation helpers: check relation entries (``has_related``)
- Versioning helper: ``next_ver``
- Default no-op trigger/composer helpers used as safe defaults

The data model is implemented with Pydantic and is intended to represent a
piece of knowledge with rich metadata, provenance, tagging and simple
relationship modelling. Most public functions and methods in this module use
Google-style docstrings describing arguments, return values and raised
exceptions.
"""

__all__ = [
    "default_trigger",
    "default_composer",
    "BaseUKF",
]

from ..utils.basic.log_utils import get_logger
from ..utils.basic.hash_utils import md5hash, fmt_hash
from ..utils.basic.serialize_utils import dumps_json, loads_json, serialize_func, deserialize_func
from ..utils.basic.debug_utils import error_str
from ..utils.basic.config_utils import HEAVEN_CM, dget, dset, dunset, dsetdef

logger = get_logger(__name__)

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_serializer, field_validator, computed_field, model_validator
from typing import Any, Callable, ClassVar, Dict, List, Literal, Optional, Set, Tuple, Union, Iterable, Type, TYPE_CHECKING
import datetime

from .ukf_utils import *

from .types import *

if TYPE_CHECKING:
    from ..utils.klop import KLOp


def default_trigger(kl, **kwargs):
    """Default trigger used as a noop predicate.

    The default trigger always returns True and can be used as a safe
    placeholder when no custom trigger function is supplied.

    Args:
        kl (BaseUKF): Knowledge object being evaluated (unused).
        **kwargs: Additional context parameters (ignored).

    Returns:
        bool: Always True.
    """
    return True


def default_composer(kl, **kwargs):
    """Default content composer that returns the raw ``content`` string.

    This function is intended as a safe default for the ``content_composers``
    mapping.

    Args:
        kl (BaseUKF): Knowledge object to compose (only ``kl.content`` is used).
        **kwargs: Additional composition parameters (ignored).

    Returns:
        str: The ``content`` attribute of ``kl``.
    """
    return kl.content


class BaseUKF(BaseModel):
    """Base model for knowledge items in the Universal Knowledge Framework (UKF).

    This Pydantic model provides a comprehensive structure for representing knowledge units
    with detailed metadata, content management, provenance tracking, and relationship modeling.
    Each attribute includes comprehensive descriptions to guide users unfamiliar with UKF
    in correctly filling knowledge records from source documents and information.

    The model is organized into logical sections:

    **Metadata**: Core identification and classification fields (name, type, version, etc.)
    **Content**: The actual knowledge and supporting structured data
    **Provenance**: Origin tracking and ownership information
    **Retrieval**: Search, classification, and access control attributes
    **Relationships**: Connections to other knowledge items and permissions
    **Lifecycle**: Time-sensitive attributes for expiration and deprecation
    **System**: Extensible fields for application-specific data and runtime statistics

    All field descriptions include practical examples and clear guidance on appropriate values,
    making this model self-documenting for users creating knowledge items from documents,
    conversations, or other information sources.

    For detailed attribute guidance, refer to the comprehensive field descriptions in the
    model definition below.
    """

    type_default: ClassVar[str] = "general"
    tags_default: ClassVar[Set[str]] = set()

    # Metadata
    name: UKFMediumTextType = Field(
        ...,
        description=("Stable, descriptive identifier for this knowledge item. Not unique, but should be distinguishable."),
        frozen=True,
    )
    notes: UKFMediumTextType = Field(
        default="",
        description=("Human-readable description. Not processed by systems."),
    )
    short_description: UKFMediumTextType = Field(
        default="",
        description=("One-sentence summary (under 200 chars) optimized for LLMs and previews. Include key purpose and scope."),
    )
    description: UKFMediumTextType = Field(
        default="",
        description=(
            "Detailed explanation of content, usage, and purpose. Include terminology, scope, etc., "
            "all the information to help humans and retrieval systems understand this knowledge."
        ),
    )
    type: UKFShortTextType = Field(
        default="general",
        description=(
            "Knowledge category for routing and processing. For example: 'experience', 'knowledge', 'resource'. "
            "A major classifier used by systems to handle different knowledge types appropriately. Typically have different classes and `content_composers`."
        ),
        frozen=True,
    )
    version: UKFShortTextType = Field(
        default="v0.1.0",
        description=(
            "Semantic version (Major.Minor.Patch). Major = breaking changes, Minor = features, "
            "Patch = fixes. Start at 'v0.1.0'. Use derive() to auto-increment."
        ),
        frozen=True,
    )
    version_notes: UKFMediumTextType = Field(
        default="",
        description=("Human-readable explanation of changes in this version. Not processed by systems."),
    )
    variant: UKFShortTextType = Field(
        default="default",
        description=(
            "Distinguishes implementations of the same knowledge. For example: languages ('en', 'zh'), "
            "complexity ('basic', 'advanced'), platforms ('web', 'mobile'), for models ('gpt4', 'claude'). "
            "Use 'default' for primary version."
        ),
        frozen=True,
    )
    variant_notes: UKFMediumTextType = Field(
        default="",
        description=("Human-readable explanation of this variant. Not processed by systems."),
    )

    # Content
    content: UKFLongTextType = Field(
        default="",
        description=("Actual knowledge content in text format. Contains core information that are directly fed to LLMs without processing."),
    )
    content_resources: UKFJsonType = Field(
        default_factory=dict,
        description=("Free-form semi-structured data supporting/replacing the content. Referenced by `content_composers` for formatting."),
    )
    content_composers: UKFJsonType = Field(
        default_factory=dict,
        description=(
            "A dictionary mapping composer names to functions, each producing a text representation of the knowledge. "
            "The functions are `f(kl: BaseUKF, **kwargs) -> str` callables that take the UKF object and optional parameters, returning a string. "
            "The produced text are used as alternatives to the raw `content` string."
        ),
    )

    # Provenance
    # Literal["system", "user", "auto", "tool", "derived", "unknown"]
    source: UKFShortTextType = Field(
        default="unknown",
        description=(
            "How this knowledge was created or obtained. Options: 'system' (built-in or fixed), 'user' (manually created), "
            "'auto' (auto-generated), 'tool' (produced by tool), 'derived' (from other knowledge), 'unknown' (others)."
        ),
        frozen=True,
    )
    parents: UKFJsonType = Field(
        default_factory=dict,
        description=("TO BE IMPROVED"),
    )
    creator: UKFShortTextType = Field(
        default="unknown",
        description=("Who or what directly created this knowledge item. Typically a user/team `id_str` or a system component name if it is auto-generated."),
        frozen=True,
    )
    owner: UKFShortTextType = Field(
        default="unknown",
        description=("Who maintains and manages this knowledge. Typically a user/team `id_str`."),
        frozen=True,
    )
    workspace: UKFShortTextType = Field(
        default="unknown",
        description=("Organizational or project context separating this knowledge from others. " "Enables multi-tenancy and knowledge isolation."),
        frozen=True,
    )

    # Retrieval
    collection: UKFShortTextType = Field(
        default="general",
        description=("Category or theme grouping within a workspace for organization and retrieval."),
        frozen=True,
    )
    tags: UKFTagsType = Field(
        default_factory=set,
        description=(
            "A set of strings. Structured tags for filtering and classification. Use format '[SLOT:value]'. "
            "e.g.,: [UKF_TYPE:knowledge], [LANGUAGE:en]. Enables advanced search like facet, etc."
        ),
        frozen=True,
    )
    synonyms: UKFSynonymsType = Field(
        default_factory=set,
        description=(
            "A set of strings. Alternative names, aliases, or related search terms. "
            "For example, 'Password Reset Guide': 'password recovery', 'account access', 'login help', 'forgot password'. "
            "Typically used for string-based search systems."
        ),
    )
    triggers: UKFJsonType = Field(
        default_factory=dict,
        description=(
            "Conditional functions determining when this knowledge activates. Each trigger receives "
            "the UKF object and context, returns True/False. Examples: 'business_hours_only', "
            "'requires_manager_role', 'valid_until_2024', 'customer_context'. Use for dynamic rules."
        ),
    )
    priority: UKFIntegerType = Field(
        default=0,
        description=("Ranking importance where higher values appear first in search results."),
    )

    # Relationships
    related: UKFRelatedType = Field(
        default_factory=set,
        description=(
            "Connections to other knowledge items as relationship tuples `(subject_id, relation, object_id, relation_id?, resources?)`. "
            "`relation_id` and `resources` are optional."
        ),
    )
    auths: UKFAuthsType = Field(
        default_factory=set,
        description=("TO BE IMPROVED: Access control permissions as `(user_id, authority)` pairs."),
    )

    # Lifecycle
    timefluid: UKFBooleanType = Field(
        default=False,
        description=("Whether this knowledge is time-sensitive. Set True if knowledge validity depends on time."),
        frozen=True,
    )
    timestamp: UKFTimestampType = Field(
        default_factory=lambda: datetime.datetime.now(tz=datetime.timezone.utc).replace(microsecond=0),
        description=(
            "When this knowledge was created (UTC, without microseconds). Used for auditing, "
            "chronological sorting, and tracking age. Automatically set; doesn't change during updates."
        ),
        frozen=True,
    )
    last_verified: UKFTimestampType = Field(
        default_factory=lambda: datetime.datetime.now(tz=datetime.timezone.utc).replace(microsecond=0),
        description=("When this content was last confirmed accurate (UTC, without microseconds). " "Update when content is edited or explicitly reviewed."),
    )
    expiration: UKFDurationType = Field(
        default=-1,
        description=("How long content remains valid after last_verified (in seconds). negative value = never expires."),
    )
    inactive_mark: UKFBooleanType = Field(
        default=False,
        description=(
            "Manual deactivation flag to immediately remove this item from active use. "
            "Set True when content is deprecated, superseded, or temporarily disabled. "
            "Overrides expiration checks - when True, item is always inactive regardless of timestamps."
        ),
    )

    # System fields
    metadata: UKFJsonType = Field(
        default_factory=dict,
        description=("Free-form application-specific data. It should never be used by systems."),
    )
    profile: UKFJsonType = Field(
        default_factory=dict,
        description=("TO BE IMPROVED: Free-form runtime usage statistics and quality metrics that evolve as knowledge is used."),
    )

    # Internal fields as utilities
    _id: Optional[str] = PrivateAttr(default=None)
    _content_hash: Optional[str] = PrivateAttr(default=None)
    _slots: Dict[str, Set[str]] = PrivateAttr(default_factory=dict)
    _type: Optional[str] = PrivateAttr(default=None)  # Discriminator for polymorphic deserialization

    # Class schema
    id_field: ClassVar[str] = "id"
    external_fields: ClassVar[Tuple[str]] = (
        "name",
        "notes",
        "short_description",
        "description",
        "type",
        "version",
        "version_notes",
        "variant",
        "variant_notes",
        "content",
        "content_resources",
        "content_composers",
        "source",
        "parents",
        "creator",
        "owner",
        "workspace",
        "collection",
        "tags",
        "synonyms",
        "triggers",
        "priority",
        "related",
        "auths",
        "timefluid",
        "timestamp",
        "last_verified",
        "expiration",
        "inactive_mark",
        "metadata",
        "profile",
    )
    internal_fields: ClassVar[Tuple[str]] = ("_id", "_content_hash", "_slots", "_type")
    property_fields: ClassVar[Tuple[str]] = (
        "id",
        "id_str",
        "content_hash",
        "content_hash_str",
        "expiration_timestamp",
        "is_inactive",
        "is_active",
    )
    identity_hash_fields: ClassVar[Tuple[str]] = (
        "type",
        "name",
        "version",
        "variant",
        "source",
        "creator",
        "owner",
        "workspace",
        "collection",
        "tags",
        "timefluid",
    )
    content_hash_fields: ClassVar[Tuple[str]] = ("content", "content_resources")
    set_fields: ClassVar[Tuple[str]] = ("tags", "synonyms", "related", "auths")
    json_func_fields: ClassVar[Tuple[str]] = ("content_composers", "triggers")
    json_data_fields: ClassVar[Tuple[str]] = ("content_resources", "parents", "metadata", "profile")

    model_config = ConfigDict(
        validate_default=True,
        validate_assignment=True,
    )

    @model_validator(mode="before")
    @classmethod
    def _inject_type_default(cls, data: Any) -> Any:
        """Inject the default type if not present in the input data."""
        if isinstance(data, dict) and "type" not in data:
            data["type"] = cls.type_default
        return data

    @field_validator("tags", mode="after")
    @classmethod
    def _inject_default_tags(cls, tags: Set[str]) -> Set[str]:
        """Automatically inject default tags and UKF_TYPE tags from class hierarchy."""
        types = set([base.__dict__.get("type_default", None) for base in cls.__mro__ if issubclass(base, BaseUKF)])
        default_tags = ptags(UKF_TYPE=list(t for t in types if t is not None)) | set(
            t for tags in [base.__dict__.get("tags_default", set()) for base in cls.__mro__ if issubclass(base, BaseUKF)] for t in tags
        )
        return set(sorted(tags.union(default_tags)))

    def __init__(self, **data):
        """Initialize BaseUKF and set the _type discriminator."""
        super().__init__(**data)
        # Set _type from the type field for polymorphic deserialization
        self._type = self.type

    @classmethod
    def model_validate(
        cls,
        obj: Any,
        *,
        strict: Optional[bool] = None,
        from_attributes: Optional[bool] = None,
        context: Optional[Dict[str, Any]] = None,
        polymorphic: bool = True,
    ) -> "BaseUKF":
        """Validate a pydantic model instance with optional polymorphic deserialization.

        This override of Pydantic's model_validate adds polymorphic deserialization
        support. When polymorphic=True (default), the method checks the 'type' field
        and returns the appropriate UKFT subclass from the registry.

        Args:
            obj: The object to validate (dict, model instance, etc.)
            strict: Whether to strictly validate the object
            from_attributes: Whether to extract data from object attributes
            context: Additional context for validation
            polymorphic: If True (default), use registry for polymorphic deserialization.
                        If False, use the class on which this method is called.

        Returns:
            BaseUKF: Validated model instance of the appropriate UKFT subclass.

        Examples:
            >>> data = {"name": "test", "type": "knowledge", ...}
            >>> # Polymorphic - returns KnowledgeUKFT
            >>> obj1 = BaseUKF.model_validate(data)
            >>> # Non-polymorphic - returns BaseUKF
            >>> obj2 = BaseUKF.model_validate(data, polymorphic=False)
        """
        # If polymorphic is disabled, use standard Pydantic validation
        if not polymorphic:
            return super().model_validate(obj, strict=strict, from_attributes=from_attributes, context=context)

        # Import here to avoid circular dependency
        from .registry import HEAVEN_UR

        # Extract type value from the object
        if isinstance(obj, dict):
            type_value = obj.get("type", getattr(cls, "type_default", "general"))
        elif isinstance(obj, BaseUKF):
            type_value = obj.type
        elif hasattr(obj, "type"):
            type_value = getattr(obj, "type", getattr(cls, "type_default", "general"))
        else:
            # Can't determine type, use current class
            return super().model_validate(obj, strict=strict, from_attributes=from_attributes, context=context)

        # Look up the appropriate class
        ukft_class = HEAVEN_UR.get(type_value)
        target_class = ukft_class if ukft_class is not None else cls
        return super(BaseUKF, target_class).model_validate(obj, strict=strict, from_attributes=from_attributes, context=context)

    # Custom serializers for ORM compatibility
    @field_serializer("tags")
    def serialize_tags(self, tags: Set[str]) -> List[str]:
        return sorted(list(tags))

    @field_serializer("synonyms")
    def serialize_synonyms(self, synonyms: Set[str]) -> List[str]:
        return sorted(list(synonyms))

    @classmethod
    def _serialize_relation_resources(cls, resource: Optional[Dict[str, Any]]) -> Optional[str]:
        if resource is not None and not isinstance(resource, dict):
            raise ValueError(f"Relation resource must be a dict or None, got {type(resource)}")
        return None if resource is None else dumps_json(resource)

    @classmethod
    def _deserialize_relation_resources(cls, resource: Optional[str]) -> Optional[Dict[str, Any]]:
        return loads_json(resource) if resource else None

    @classmethod
    def _serialize_relation(cls, relation: Tuple[int, str, int, Optional[int], Optional[Dict[str, Any]]]) -> Tuple[int, str, int, Optional[int], Optional[str]]:
        return (
            int(relation[0]),  # subject_id
            relation[1],  # relation
            int(relation[2]),  # object_id
            None if len(relation) <= 3 else relation[3],  # relation_id
            None if len(relation) <= 4 else cls._serialize_relation_resources(relation[4]),  # relation_resources
        )

    @classmethod
    def _deserialize_relation(
        cls, relation: Tuple[int, str, int, Optional[int], Optional[str]]
    ) -> Tuple[int, str, int, Optional[int], Optional[Dict[str, Any]]]:
        return (
            fmt_hash(relation[0]),  # subject_id
            relation[1],  # relation
            fmt_hash(relation[2]),  # object_id
            None if len(relation) <= 3 else relation[3],  # relation_id
            None if len(relation) <= 4 else cls._deserialize_relation_resources(relation[4]),  # relation_resources
        )

    @field_serializer("related")
    def serialize_related(
        self, related: Set[Tuple[int, str, int, Optional[int], Optional[str]]]
    ) -> List[Tuple[int, str, int, Optional[int], Optional[Dict[str, Any]]]]:
        """\
        Notice that the related is reversed:
            Since Set does not support Dict (relation_resources) as items, the relation tuples should actually be
            deserialized (str -> json) during `serialize_related` (export from Python object to JSON).
        """
        return sorted(list(self.__class__._deserialize_relation(relation) for relation in related))

    @field_serializer("auths")
    def serialize_auths(self, auths: Set[Tuple[str, str]]) -> List[Tuple[str, str]]:
        return sorted(list(auths))

    @field_serializer("triggers")
    def serialize_triggers(self, triggers: Dict[str, Callable]) -> Dict[str, Dict]:
        return {k: serialize_func(v) for k, v in triggers.items()}

    @field_validator("triggers", mode="before")
    @classmethod
    def validate_triggers(cls, value):
        """Validate and deserialize triggers."""
        if isinstance(value, dict):
            return {k: (deserialize_func(v) if isinstance(v, dict) else v) for k, v in value.items()}
        return value

    @field_serializer("content_composers")
    def serialize_content_composers(self, composers: Dict[str, Callable]) -> Dict[str, Dict]:
        return {k: serialize_func(v) for k, v in composers.items()}

    @field_validator("content_composers", mode="before")
    @classmethod
    def validate_content_composers(cls, value):
        """Validate and deserialize content composers."""
        if isinstance(value, dict):
            return {k: (deserialize_func(v) if isinstance(v, dict) else v) for k, v in value.items()}
        return value

    @field_serializer("timestamp")
    def serialize_timestamp(self, dt: datetime.datetime) -> str:
        return dt.replace(microsecond=0).isoformat()

    @field_serializer("last_verified")
    def serialize_last_verified(self, dt: datetime.datetime) -> str:
        return dt.replace(microsecond=0).isoformat()

    @field_serializer("expiration")
    def serialize_expiration(self, value: datetime.timedelta) -> int:
        return int(value.total_seconds())

    @field_serializer("expiration_timestamp")  # computed field
    def serialize_expiration_timestamp(self, dt: datetime.datetime) -> str:
        return dt.replace(microsecond=0).isoformat()

    # Class methods for backward compatibility with ORM adapter
    @classmethod
    def deserialize_tags(cls, value: Iterable[str]) -> Set[str]:
        """Backward compatibility method - validation is now handled by UKFTagsType."""
        return UKFTagsType._validate(value)

    @classmethod
    def deserialize_synonyms(cls, value: Iterable[str]) -> Set[str]:
        """Backward compatibility method - validation is now handled by UKFSynonymsType."""
        return UKFSynonymsType._validate(value)

    @classmethod
    def deserialize_related(cls, value: Iterable) -> Set:
        """Backward compatibility method - validation is now handled by UKFRelatedType."""
        return UKFRelatedType._validate(value)

    @classmethod
    def deserialize_auths(cls, value: Iterable) -> Set:
        """Backward compatibility method - validation is now handled by UKFAuthsType."""
        return UKFAuthsType._validate(value)

    @classmethod
    def deserialize_triggers(cls, value) -> Dict[str, Callable]:
        """Backward compatibility method - deserialize function dictionaries."""
        return {k: (deserialize_func(v) if isinstance(v, Dict) else v) for k, v in value.items()}

    @classmethod
    def deserialize_content_composers(cls, value) -> Dict[str, Callable]:
        """Backward compatibility method - deserialize function dictionaries."""
        return {k: (deserialize_func(v) if isinstance(v, Dict) else v) for k, v in value.items()}

    @classmethod
    def schema(cls) -> Dict[str, Any]:
        schema = dict()
        for field_name in cls.external_fields:
            field_type = cls.model_fields[field_name].annotation
            schema[field_name] = field_type
        return schema

    def _resetinternal_fields(self):
        """\
        Reset internal fields for re-computation.

        Clears cached values for id, content_hash, and slots to force
        recalculation when accessed next time.
        """
        self._id = None
        self._content_hash = None
        self._slots.clear()

    @computed_field
    @property
    def id(self) -> int:
        """Compute a deterministic integer identifier for the item.

        The identifier is computed by hashing a selection of identity fields
        (see :pyattr:`identity_hash_fields`) and cached on the instance. The
        cached value is cleared by :meth:`_resetinternal_fields` when needed.

        Returns:
            int: Integer hash value derived from identity fields.
        """
        if self._id is None:
            identity_fields = {k: getattr(self, k) for k in self.identity_hash_fields}
            identity_fields["tags"] = sorted(list(identity_fields["tags"]))
            self._id = md5hash(identity_fields)
        return self._id

    @computed_field
    @property
    def id_str(self) -> str:
        """Return the ``id`` value formatted as a zero-padded string.

        Uses `fmt_hash` to produce a fixed-width, human-safe string
        representation of the integer id.

        Returns:
            str: Zero-padded string version of :pyattr:`id`.
        """
        return fmt_hash(self.id)

    @computed_field
    @property
    def content_hash(self) -> int:
        """Compute a hash of the content-related fields for change detection.

        The hash covers :pyattr:`content` and :pyattr:`content_resources` and
        is cached on the instance. Cache is invalidated by
        :meth:`_resetinternal_fields`.

        Returns:
            int: Integer hash representing the content state.
        """
        if self._content_hash is None:
            content_hash_fields = {k: getattr(self, k) for k in self.content_hash_fields}
            self._content_hash = md5hash(content_hash_fields)
        return self._content_hash

    @computed_field
    @property
    def content_hash_str(self) -> str:
        """Return the content hash formatted as a zero-padded string.

        Returns:
            str: String representation produced by `fmt_hash` for
                :pyattr:`content_hash`.
        """
        return fmt_hash(self.content_hash)

    @computed_field
    @property
    def expiration_timestamp(self) -> datetime.datetime:
        """Compute the UTC timestamp when the item expires.

        If :pyattr:`expiration` is negative the function returns a distant
        future sentinel (year 2500) indicating no automatic expiration.

        Returns:
            datetime.datetime: UTC datetime when the item becomes expired.
        """
        MAX_DATETIME = datetime.datetime.fromisoformat("2500-01-01")
        if self.expiration < datetime.timedelta(0):
            return MAX_DATETIME
        return self.last_verified + datetime.timedelta(seconds=self.expiration)

    @property
    def slots(self) -> Dict[str, Set[str]]:
        """Return a mapping from tag slots to their set of values.

        Parses :pyattr:`tags` and groups values by slot name (the left-hand
        side of a ``[SLOT:value]`` tag). The result is cached in the private
        attribute :pyattr:`_slots` for efficiency.

        Returns:
            Dict[str, Set[str]]: Mapping of slot name to set of values.
        """
        if not self._slots:
            self._slots = gtags(self.tags)
        return self._slots

    def has_tag(
        self,
        slot: str,
        operator: TagOperator = "ANY_OF",
        value: Optional[Union[Iterable, str, Any]] = None,
    ):
        """Check whether this item's tags satisfy a named condition for ``slot``.

        This is a convenience wrapper around the module-level :func:`has_tag`
        that uses this instance's :pyattr:`tags` set.

        Args:
            slot (str): Tag slot to check.
            operator (TagOperator): Operator to apply (see module-level
                :func:`has_tag` for supported operators).
            value (Optional[Union[Iterable, str, Any]]): Values to compare
                against for non-unary operators.

        Returns:
            bool: True if the condition holds for this item's tags.
        """
        return has_tag(self.tags, slot=slot, operator=operator, value=value)

    def has_related(
        self,
        subject_id: Optional[Union[int, Iterable[int]]] = None,
        relation: Optional[Union[str, Iterable[str]]] = None,
        object_id: Optional[Union[int, Iterable[int]]] = None,
        relation_id: Optional[Union[int, Iterable[int]]] = None,
        related_to_id: Optional[Union[int, Iterable[int]]] = None,
    ) -> bool:
        """Return True if any relation on this item satisfies the provided filters.

        This is a thin wrapper around the module-level :func:`has_related` that
        operates on :pyattr:`related`.

        Args:
            subject_id (Optional[Union[int, Iterable[int]]]): Filter for
                subject id(s).
            relation (Optional[Union[str, Iterable[str]]]): Filter for relation
                name(s).
            object_id (Optional[Union[int, Iterable[int]]]): Filter for object
                id(s).
            relation_id (Optional[Union[int, Iterable[int]]]): Filter for
                relation id(s).
            related_to_id (Optional[Union[int, Iterable[int]]]): Matches when
                either subject or object id is included in this set.

        Returns:
            bool: True when a matching relation exists.
        """
        return has_related(
            self.related,
            subject_id=subject_id,
            relation=relation,
            object_id=object_id,
            relation_id=relation_id,
            related_to_id=related_to_id,
        )

    @computed_field
    @property
    def is_inactive(self) -> bool:
        """Return True when the item is considered inactive.

        An item is inactive when either :pyattr:`inactive_mark` is True or the
        current UTC time is past the value returned by
        :pyattr:`expiration_timestamp` (when expiration is enabled).

        Returns:
            bool: True when the item is inactive.
        """
        if self.inactive_mark:
            return True
        # Negative expiration disables automatic expiration
        if self.expiration < datetime.timedelta(0):
            return False
        return datetime.datetime.now(tz=datetime.timezone.utc) > self.expiration_timestamp

    @computed_field
    @property
    def is_active(self) -> bool:
        """Return True when the item is active (not inactive).

        Returns:
            bool: Negation of :pyattr:`is_inactive`.
        """
        return not self.is_inactive

    def set_composer(self, name: str, composer: Callable):
        """Add or update a content composer in :pyattr:`content_composers`.

        Args:
            name (str): Name of the composer.
            composer (Callable): Callable that takes a :class:`BaseUKF`
                instance and returns a string representation.

        Raises:
            ValueError: If ``name`` is empty or ``composer`` is not callable.
        """
        self.content_composers[name] = composer

    def update_composers(self, composers: Optional[Dict[str, Callable]] = None):
        """Update multiple content composers in :pyattr:`content_composers`.

        Args:
            composers (Optional[Dict[str, Callable]]): Mapping of composer names to
                callables. If None, no changes are made.

        Raises:
            ValueError: If any name is empty or any composer is not callable.
        """
        self.content_composers.update(composers or dict())

    def text(self, composer: Optional[Union[str, Callable]] = "default", **kwargs) -> str:
        """Return a text representation produced by a composer.

        The ``composer`` parameter may be a callable or the name of a composer
        in :pyattr:`content_composers`. If ``composer`` is not found the raw
        :pyattr:`content` string is returned. Any exceptions raised by a
        composer are logged and the raw content is returned as a fallback.

        Args:
            composer (Optional[Union[str, Callable]]): Composer name or callable.
            **kwargs: Passed through to the composer callable.

        Returns:
            str: Composed or raw textual representation.
        """
        if isinstance(composer, Callable):
            return composer(self, **kwargs)
        content_composers = {"default": default_composer} | self.content_composers
        if (composer is None) or (composer not in content_composers):
            return self.content
        try:
            return content_composers[composer](self, **kwargs)
        except Exception as e:
            logger.error(f"Error occurred while composing text: {error_str(e)}.")
            return self.content

    def __eq__(self, other: Any) -> bool:
        """Equality comparison using :pyattr:`id`.

        Two instances are considered equal when they are instances of the same
        class and their computed :pyattr:`id` values are identical.

        Args:
            other (Any): Object to compare.

        Returns:
            bool: True when objects represent the same knowledge id.
        """
        if not isinstance(other, self.__class__):
            return False
        return self.id == other.id

    def __lt__(self, other: "BaseUKF") -> bool:
        """Ordering comparison used for sorting by priority.

        The implementation treats higher :pyattr:`priority` values as "less"
        to allow reverse-priority ordering when using Python's default
        ascending sort.

        Args:
            other (BaseUKF): Other item to compare.

        Returns:
            bool: True when this item should sort before ``other``.
        """
        return self.priority > other.priority

    def __hash__(self) -> int:
        """Return a hash derived from :pyattr:`id`.

        Returns:
            int: Integer hash value.
        """
        return self.id

    def __str__(self) -> str:
        """Return a compact multi-line human readable representation.

        The representation shows a truncated content preview and a short form
        of the string id.

        Returns:
            str: Readable summary of the object.
        """
        text = self.text()
        content_repr = repr(text if len(text) <= 128 else f"{text[:125]}...")
        id_repr = f"{self.id_str}"[:8] + "..." + f"{self.id_str}"[-8:]
        return f"{self.__class__.__name__}(name='{self.name}', version='{self.version}', variant='{self.variant}', type='{self.type}',\n\ttags={self.tags},\n\tcontent={content_repr},\n\tsynonyms={self.synonyms},\n\tid={id_repr}\n)"

    def __repr__(self) -> str:
        """Return the same value as :meth:`__str__` for interactive display."""
        return str(self)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the model to a plain dictionary for storage or transport.

        Returns:
            Dict[str, Any]: Dictionary serialization excluding internal fields.
        """
        return self.model_dump(exclude=self.internal_fields)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], *, polymorphic: bool = True) -> "BaseUKF":
        """Create a :class:`BaseUKF` instance from a dictionary.

        This method supports polymorphic deserialization: if the `type` field
        in the data matches a registered UKFT class in HEAVEN_UR, an instance
        of that specific subclass will be returned instead of a generic BaseUKF.

        Args:
            data (Dict[str, Any]): Dictionary produced by :meth:`to_dict` or an
                external source.
            polymorphic (bool): If True (default), use registry to return the
                appropriate subclass. If False, use the class on which this
                method is called.

        Returns:
            BaseUKF: Validated model instance of the appropriate UKFT subclass.

        Examples:
            >>> data = {"name": "test", "type": "knowledge", ...}
            >>> obj = BaseUKF.from_dict(data)  # Returns KnowledgeUKFT
            >>> obj2 = BaseUKF.from_dict(data, polymorphic=False)  # Returns BaseUKF
        """
        # If polymorphic is disabled, use the current class directly
        if not polymorphic:
            return cls.model_validate(data)

        # Import here to avoid circular dependency
        from .registry import HEAVEN_UR

        # Check if we should use a specific UKFT subclass
        type_value = data.get("type", getattr(cls, "type_default", "general"))
        ukft_class = HEAVEN_UR.get(type_value)

        # Use the registered class if available, otherwise use the current class
        target_class = ukft_class if ukft_class is not None else cls

        return target_class.model_validate(data)

    @classmethod
    def from_ukf(cls, ukf: "BaseUKF", *, polymorphic: bool = True, override_type: bool = False) -> "BaseUKF":
        """Create a :class:`BaseUKF` instance from another instance.

        This method supports polymorphic deserialization: if the source UKF's
        type matches a registered UKFT class in HEAVEN_UR, an instance of that
        specific subclass will be returned.

        Args:
            ukf (BaseUKF): Instance of the same or a derived class.
            polymorphic (bool): If True (default), use registry to return the
                appropriate subclass. If False, use the class on which this
                method is called, allowing intentional type conversion (e.g.,
                upcasting PromptUKFT to ResourceUKFT).
                Usually, this is used when loading unknown types from storage.
            override_type (bool): If True and polymorphic=False, override the
                'type' field to match the target class. Useful for true
                downcasting where you want to change the type field.
                Notice that type is part of the UKF identity, so overriding it
                will also change the computed id, making this a different
                knowledge item, which could be undesired in some scenarios.
                Usually, this is used when defining new sub-type UKFTs.
                If polymorphic=True, this parameter is ignored.

        Returns:
            BaseUKF: Validated model instance of the appropriate UKFT subclass.

        Examples:
            >>> prompt = PromptUKFT(name="test", ...)
            >>> # Preserve original type
            >>> copy1 = BaseUKF.from_ukf(prompt)
            >>> # copy1.type == "prompt" and type(copy1) == PromptUKFT
            >>> # Intentional downcast to parent type (keeps original type field)
            >>> resource = ResourceUKFT.from_ukf(prompt, polymorphic=False)
            >>> # resource.type == "prompt" and type(resource) == ResourceUKFT
            >>> # True downcast with type field override
            >>> resource2 = ResourceUKFT.from_ukf(prompt, polymorphic=False, override_type=True)
            >>> # resource2.type == "resource" and type(resource2) == ResourceUKFT
        """
        if not isinstance(ukf, BaseUKF):
            raise ValueError(f"Cannot create {cls.__name__} from {type(ukf).__name__}.")

        # Get the data
        data = ukf.model_dump()

        # If polymorphic is disabled and override_type is True, update the type field
        if not polymorphic and override_type:
            data["type"] = getattr(cls, "type_default", "general")

        # If polymorphic is disabled, use the current class directly
        if not polymorphic:
            return cls.model_validate(data, polymorphic=False)

        # Import here to avoid circular dependency
        from .registry import HEAVEN_UR

        # Check if we should use a specific UKFT subclass
        type_value = ukf.type
        ukft_class = HEAVEN_UR.get(type_value)

        # Use the registered class if available, otherwise use the current class
        target_class = ukft_class if ukft_class is not None else cls

        return target_class.model_validate(data)

    def get(self, key_path: str, default: Any = None) -> Any:
        """\
        Retrieve a nested value from the BaseUKF's `content_resources` using a dot-separated key path.

        Args:
            key_path (str): Dot-separated path to the desired value (e.g., "level1.level2.key").
            default (Any): Value to return if the key path does not exist.

        Returns:
            Any: The value found at the specified key path, or the default if not found.
        """
        return dget(self.content_resources, key_path, default)

    def set(self, key_path: str, value: Any) -> bool:
        """\
        Set a nested value in the BaseUKF's `content_resources` using a dot-separated key path.

        Args:
            key_path (str): Dot-separated path to set the value (e.g., "level1.level2.key").
            value (Any): The value to set at the specified key path.

        Returns:
            bool: True if the value was set successfully, False otherwise.
        """
        return dset(self.content_resources, key_path, value)

    def unset(self, key_path: str) -> bool:
        """\
        Remove a nested value from the BaseUKF's `content_resources` using a dot-separated key path.

        Args:
            key_path (str): Dot-separated path to the value to remove (e.g., "level1.level2.key").

        Returns:
            bool: True if the value was removed successfully, False otherwise.
        """
        return dunset(self.content_resources, key_path)

    def setdef(self, key_path: str, value: Any) -> bool:
        """\
        Set a nested value in the BaseUKF's `content_resources` only if the key path does not already exist.

        Args:
            key_path (str): Dot-separated path to set the value (e.g., "level1.level2.key").
            value (Any): The value to set at the specified key path.

        Returns:
            bool: True if the value was set successfully, False if the key path already exists.
        """
        return dsetdef(self.content_resources, key_path, value)

    def set_inactive(self):
        """Mark the item as inactive by setting :pyattr:`inactive_mark` to True."""
        self.inactive_mark = True

    def unset_inactive(self):
        """Clear the manual inactive flag by setting :pyattr:`inactive_mark` to False."""
        self.inactive_mark = False

    def set_active(self):
        """Mark the item as active by setting :pyattr:`inactive_mark` to False."""
        self.inactive_mark = False

    def set_trigger(self, name: str, trigger: Callable):
        """Add or update a trigger callable in :pyattr:`triggers`.

        Args:
            name (str): Name of the trigger.
            trigger (Callable): Callable that takes a :class:`BaseUKF`
                instance and returns a boolean.
        """
        self.triggers[name] = trigger

    def update_triggers(self, triggers: Optional[Dict[str, Callable]] = None):
        """Merge new trigger callables into the :pyattr:`triggers` mapping.

        Args:
            triggers (Optional[Dict[str, Callable]]): Mapping of name to callable
                to add or update. If None, no changes are made.
        """
        self.triggers.update(triggers or dict())

    def eval_triggers(
        self,
        triggers: List[str] = None,
        contexts: Optional[Dict] = None,
        aggregate: Literal["ANY", "ALL", False] = "ALL",
    ) -> Union[Dict[str, bool], bool]:
        """Evaluate one or more named triggers with optional context.

        Args:
            triggers (List[str], optional): Names of triggers to eval_triggers. If
                None or empty, an empty result is returned (or ``True`` when
                aggregated as described below).
            contexts (Optional[Dict], optional): Mapping from trigger name to a
                context dict passed as keyword arguments to the trigger.
            aggregate (Literal["ANY", "ALL", False]): If ``False`` the
                function returns a dictionary of individual boolean results.
                If ``"ALL"`` the function returns ``True`` only if all
                evaluated triggers return ``True``. If ``"ANY"`` the
                function returns ``True`` when any trigger returns ``True``.

        Returns:
            Union[Dict[str, bool], bool]: Individual results or an aggregated
            boolean depending on ``aggregate``.
        """
        contexts = contexts or dict()
        triggers = triggers or dict()
        aug_triggers = {"default": default_trigger} | self.triggers
        result = {trigger: bool(aug_triggers.get(trigger)(self, **contexts.get(trigger))) for trigger in triggers if trigger in aug_triggers}
        return result if not aggregate else ((len(result) == 0) or (any(result.values()) if aggregate == "ANY" else all(result.values())))

    def eval_filter(self, filter: Optional[Union[Dict[str, Any], "KLOp"]] = None, **kwargs) -> bool:
        """Evaluate whether this BaseUKF object satisfies a KLOp expression.

        This method evaluates filter conditions in-memory by checking the object's
        field values against the filter criteria. It supports all KLOp operators
        and handles both parsed JSON IR expressions and KLOp objects.

        Args:
            filter: Either a parsed KLOp.expr() dict or None. If None, only kwargs are used.
            **kwargs: Additional field constraints that are ANDed with the filter.

        Returns:
            bool: True if the object satisfies all filter conditions, False otherwise.

        Example:
            >>> ukf = BaseUKF(name="test", priority=50, status="active")
            >>> ukf.eval_filter(priority=50)  # Simple equality
            True
            >>> ukf.eval_filter(priority=KLOp.GT(40))  # Comparison operator
            True
            >>> ukf.eval_filter(priority=KLOp.BETWEEN(0, 100), status="active")  # Combined
            True
            >>> from ahvn.utils.klop import KLOp
            >>> expr = KLOp.expr(priority=KLOp.GT(40))
            >>> ukf.eval_filter(expr)  # Using parsed expression
            True
        """
        from ahvn.utils.klop import KLOp

        # Build combined filter expression
        if filter is None:
            if not kwargs:
                return True  # No filter means match all
            expr = KLOp.expr(**kwargs)
        else:
            if kwargs:
                # Combine filter and kwargs with AND
                kwargs_expr = KLOp.expr(**kwargs)
                expr = {"AND": [filter, kwargs_expr]}
            else:
                expr = filter

        return self._eval_expr(expr)

    def _eval_expr(self, expr: Any) -> bool:
        """Recursively evaluate a filter expression against this object.

        Args:
            expr: A parsed filter expression (dict) or value.

        Returns:
            bool: True if the expression evaluates to True.
        """
        # Handle ellipsis (field existence check)
        if expr is ...:
            return True  # Object exists

        # Handle dict expressions
        if not isinstance(expr, dict):
            raise ValueError(f"Invalid filter expression: {expr}")

        # Handle logical operators
        if "AND" in expr:
            return all(self._eval_expr(e) for e in expr["AND"])

        if "OR" in expr:
            return any(self._eval_expr(e) for e in expr["OR"])

        if "NOT" in expr:
            return not self._eval_expr(expr["NOT"])

        # Handle field expressions
        for key, value in expr.items():
            if key.startswith("FIELD:"):
                field_name = key[6:]  # Strip "FIELD:" prefix
                return self._eval_field(field_name, value)

        raise ValueError(f"Invalid filter expression: {expr}")

    def _eval_field(self, field_name: str, condition: Any) -> bool:
        """Evaluate a field condition against this object's field value.

        Args:
            field_name: The name of the field to check.
            condition: The condition expression (dict or value).

        Returns:
            bool: True if the field satisfies the condition.
        """
        # Check if field exists
        if not hasattr(self, field_name):
            return False

        field_value = getattr(self, field_name)

        # Handle ellipsis (field existence check)
        if condition is ...:
            return field_value is not None

        # Handle dict conditions
        if not isinstance(condition, dict):
            raise ValueError(f"Invalid field condition: {condition}")

        # Handle logical operators within field
        if "AND" in condition:
            return all(self._eval_field(field_name, c) for c in condition["AND"])

        if "OR" in condition:
            return any(self._eval_field(field_name, c) for c in condition["OR"])

        if "NOT" in condition:
            return not self._eval_field(field_name, condition["NOT"])

        # Handle comparison operators
        if "==" in condition:
            return field_value == condition["=="]

        if "!=" in condition:
            return field_value != condition["!="]

        if "<" in condition:
            return field_value < condition["<"]

        if "<=" in condition:
            return field_value <= condition["<="]

        if ">" in condition:
            return field_value > condition[">"]

        if ">=" in condition:
            return field_value >= condition[">="]

        # Handle IN operator
        if "IN" in condition:
            values = condition["IN"]
            if not isinstance(values, (list, set, tuple)):
                values = [values]
            return field_value in values

        # Handle pattern matching
        if "LIKE" in condition:
            import re

            # Convert SQL LIKE pattern to regex
            pattern = condition["LIKE"].replace("%", ".*").replace("_", ".")
            return bool(re.match(pattern, str(field_value)))

        if "ILIKE" in condition:
            import re

            # Convert SQL ILIKE pattern to regex (case-insensitive)
            pattern = condition["ILIKE"].replace("%", ".*").replace("_", ".")
            return bool(re.match(pattern, str(field_value), re.IGNORECASE))

        # Handle NF operator (normalized form for tags/auths)
        if "NF" in condition:
            # This is complex - for now, just check if field_value contains the expected dict
            nf_dict = condition["NF"]
            if not isinstance(field_value, (list, set)):
                return False
            # Check if any item in field_value matches all key-value pairs in nf_dict
            for item in field_value:
                if isinstance(item, dict) and all(item.get(k) == v for k, v in nf_dict.items()):
                    return True
            return False

        # Handle JSON operator (nested field access)
        if "JSON" in condition:
            json_cond = condition["JSON"]

            # New format: JSON contains multiple key-value pairs
            # Need to check all conditions (AND semantics)
            for path, expected_value in json_cond.items():
                # Navigate nested path
                current = field_value
                for key in path.split("."):
                    if isinstance(current, dict) and key in current:
                        current = current[key]
                    else:
                        return False  # Path doesn't exist

                # Check value
                if expected_value is ...:
                    if current is None:
                        return False
                elif isinstance(expected_value, dict):
                    if not self._eval_field_value(current, expected_value):
                        return False
                else:
                    if current != expected_value:
                        return False

            # All conditions passed
            return True

        raise ValueError(f"Unknown operator in condition: {condition}")

    def _eval_field_value(self, value: Any, condition: dict) -> bool:
        """Helper to evaluate a value against a condition dict.

        Args:
            value: The value to check.
            condition: The condition dict with operators.

        Returns:
            bool: True if value satisfies condition.
        """
        # Handle logical operators
        if "AND" in condition:
            return all(self._eval_field_value(value, c) for c in condition["AND"])
        if "OR" in condition:
            return any(self._eval_field_value(value, c) for c in condition["OR"])
        if "NOT" in condition:
            return not self._eval_field_value(value, condition["NOT"])

        # Handle comparison operators
        if "==" in condition:
            return value == condition["=="]
        if "!=" in condition:
            return value != condition["!="]
        if "<" in condition:
            return value < condition["<"]
        if "<=" in condition:
            return value <= condition["<="]
        if ">" in condition:
            return value > condition[">"]
        if ">=" in condition:
            return value >= condition[">="]
        if "IN" in condition:
            return value in condition["IN"]
        return False

    def clone(self, **updates) -> "BaseUKF":
        """Return a deep-copied model updated with ``updates``.

        The returned instance has internal caches reset so identity and
        content hashes are recomputed on demand.

        Args:
            **updates: Field values to override in the cloned instance.
                For dict/list/set fields, use `upd_<field>` to update items instead of overwriting.
                Typical fields that support this are :pyattr:`tags`, :pyattr:`synonyms`,
                :pyattr:`related`, :pyattr:`auths`, :pyattr:`triggers`, :pyattr:`content_composers`,
                :pyattr: `content_resources`, :pyattr:`metadata`, etc.

        Returns:
            BaseUKF: New instance with the requested updates applied.
        """
        upd_fields = {k[4:]: v for k, v in updates.items() if k.startswith("upd_")}
        other_fields = {k: v for k, v in updates.items() if not k.startswith("upd_")}
        new_knowledge = self.model_copy(update=other_fields, deep=True)
        for field, items in upd_fields.items():
            getattr(new_knowledge, field).update(items)
        new_knowledge._resetinternal_fields()
        return new_knowledge

    def derive(self, **updates) -> "BaseUKF":
        """Create a derived item with incremented version and provenance.

        The derived copy has its :pyattr:`version` bumped using
        :func:`next_ver`, :pyattr:`source` set to ``"derived"`` and the
        original id recorded in :pyattr:`parents`.

        Args:
            **updates: Additional field updates to apply to the derived item.
                For dict/list/set fields, use `upd_<field>` to update items instead of overwriting.
                Typical fields that support this are :pyattr:`tags`, :pyattr:`synonyms`,
                :pyattr:`related`, :pyattr:`auths`, :pyattr:`triggers`, :pyattr:`content_composers`,
                :pyattr: `content_resources`, :pyattr:`metadata`, etc.

        Returns:
            BaseUKF: Derived instance.
        """
        new_knowledge = self.clone(
            **(
                {
                    "version": next_ver(self.version),
                    "version_notes": f"Derived from {self.name}:{self.version} ({self.id})",
                    "variant_notes": "",
                    "source": "derived",
                    "timestamp": datetime.datetime.now(tz=datetime.timezone.utc).replace(microsecond=0),
                    "last_verified": datetime.datetime.now(tz=datetime.timezone.utc).replace(microsecond=0),
                    "parents": {"derived_from": self.id},
                }
                | updates
            )
        )
        return new_knowledge

    def link(
        self,
        kl: "BaseUKF",
        dir: Literal["subject", "object", "both"] = "object",
        rel: str = "related",
        rel_kid: Optional[int] = None,
        relation_resources: Optional[Any] = None,
        inv_link=False,
    ):
        """Add a lightweight relation between this item and ``kl``.

        Relation tuples are inserted into :pyattr:`related` using the
        serialized form for ``relation_resources``. The ``dir`` parameter
        controls whether this item is the subject, object or both.

        Args:
            kl (BaseUKF): Target knowledge item.
            dir (Literal["subject","object","both"]): Direction of the
                relation where ``"object"`` means ``self -> kl``.
            rel (str): Relation name.
            rel_kid (Optional[int]): Optional relation id.
            relation_resources (Optional[Any]): Additional relation metadata.
            inv_link (bool): When True also add reciprocal entries on ``kl``.
        """
        relation_dumped = self.__class__._serialize_relation_resources(relation_resources)
        if dir in ["object", "both"]:
            self.related.add((self.id, rel, kl.id, rel_kid, relation_dumped))
            if inv_link:
                kl.related.add((kl.id, rel, self.id, rel_kid, relation_dumped))
        if dir in ["subject", "both"]:
            self.related.add((kl.id, rel, self.id, rel_kid, relation_dumped))
            if inv_link:
                kl.related.add((self.id, rel, kl.id, rel_kid, relation_dumped))

    def obj_ids(self, rel: Optional[str] = None) -> List[str]:
        """Return object ids for relations where this item is the subject.

        Args:
            rel (Optional[str]): If provided, only relations matching this
                relation name are included.

        Returns:
            List[str]: Sequence of object ids.
        """
        return [o for s, r, o, _, _ in self.related if ((rel is None) or (r == rel)) and s == self.id]

    def sub_ids(self, rel: Optional[str] = None) -> List[str]:
        """Return subject ids for relations where this item is the object.

        Args:
            rel (Optional[str]): Optional relation name filter.

        Returns:
            List[str]: Sequence of subject ids.
        """
        return [s for s, r, o, _, _ in self.related if ((rel is None) or (r == rel)) and o == self.id]

    def grant(self, user_id: int, authority: str):
        """Grant an authority by adding [user:authority] tag.

        Args:
            user_id (int): User identifier.
            authority (str): Permission or role string.
        """
        # Add auth tag to the tags set
        auth_tag = f"[{user_id}:{authority}]"
        self.tags.add(auth_tag)
        # Also maintain backward compatibility with auths field
        self.auths.add((user_id, authority))

    def revoke(self, user_id: int, authority: str):
        """Remove an authority by removing [user:authority] tag.

        Args:
            user_id (int): User identifier.
            authority (str): Permission or role string.
        """
        # Remove auth tag from the tags set
        auth_tag = f"[{user_id}:{authority}]"
        self.tags.discard(auth_tag)
        # Also maintain backward compatibility with auths field
        self.auths.discard((user_id, authority))

    def has_authority(self, user_id: int, authority: str) -> bool:
        """Return True when [user:authority] tag is present.

        Args:
            user_id (int): User identifier.
            authority (str): Authority string.

        Returns:
            bool: True if the authority is granted to the user.
        """
        # Check for auth tag in tags set
        auth_tag = f"[{user_id}:{authority}]"
        return auth_tag in self.tags or (user_id, authority) in self.auths

    def add_synonyms(self, synonyms: Iterable[str]) -> None:
        """Append new synonyms into the :pyattr:`synonyms` set.

        Args:
            synonyms (Iterable[str]): Iterable of synonym strings to add.
        """
        for s in synonyms:
            if s is not None:
                self.synonyms.add(str(s).strip())

    def remove_synonyms(self, synonyms: Iterable[str]) -> None:
        """Remove synonyms from the :pyattr:`synonyms` set.

        Args:
            synonyms (Iterable[str]): Iterable of synonym strings to remove.
        """
        for s in synonyms:
            if s is not None:
                self.synonyms.discard(str(s).strip())

    def signed(self, system: bool = False, verified: bool = True, **kwargs):
        """\
        Sign the knowledge item with default provenance information.

        Args:
            system (bool): Whether the knowledge is created by the system. Defaults to False.
            verified (bool): Whether the knowledge is verified as accurate. Defaults to True.
            **kwargs: Additional provenance fields to override.
                Specifically the following kwargs are set:
                - source: set to the provided source, or "system" if system is True, or existing source, or "user" if existing source is "unknown"
                - creator: set to the provided creator, or "system" if system is True, or existing creator, or current user id from HEAVEN_CM if existing creator is "unknown"
                - owner: set to the provided owner, or "system" if system is True, or existing owner, or current user id from HEAVEN_CM if existing owner is "unknown"
                - workspace: set to the provided workspace, or existing workspace
                - inactive_mark: set to the provided inactive_mark, or not verified
                - last_verified: set to the provided last_verified, or current UTC time without microseconds if verified is True, or existing last_verified

        Returns:
            BaseUKF: A cloned knowledge item with updated provenance fields.
        """
        updated_kwargs = {k: v for k, v in kwargs.items() if k not in ["source", "creator", "owner", "workspace", "inactive_mark", "last_verified"]} | {
            "source": kwargs.get("source", "system" if system else (self.source if self.source != "unknown" else "user")),
            "creator": kwargs.get("creator", "system" if system else (self.creator if self.creator != "unknown" else HEAVEN_CM.get("user.user_id", "admin"))),
            "owner": kwargs.get("owner", "system" if system else (self.owner if self.owner != "unknown" else HEAVEN_CM.get("user.user_id", "admin"))),
            "workspace": kwargs.get("workspace", self.workspace),
            "inactive_mark": kwargs.get("inactive_mark", not verified),
            "last_verified": kwargs.get(
                "last_verified", datetime.datetime.now(tz=datetime.timezone.utc).replace(microsecond=0) if verified else self.last_verified
            ),
        }
        return self.clone(**updated_kwargs)
