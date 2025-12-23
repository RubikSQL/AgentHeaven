__all__ = [
    "ORMUKFAdapter",
]

from ahvn.utils.db.types import ExportableEntity, get_base
from .base import BaseUKFAdapter

from ..utils.db import *
from ..utils.basic.config_utils import HEAVEN_CM
from ..utils.basic.hash_utils import fmt_short_hash, md5hash

from ..ukf.ukf_utils import tag_t
from ..ukf.base import BaseUKF

from typing import Any, Dict, Type, Iterable, List
from ..utils.deps import deps

# Lazy import sqlalchemy
_sqlalchemy = None


def get_sqlalchemy():
    global _sqlalchemy
    if _sqlalchemy is None:
        _sqlalchemy = deps.load("sqlalchemy")
    return _sqlalchemy


def Column(*args, **kwargs):
    return get_sqlalchemy().Column(*args, **kwargs)


def Index(*args, **kwargs):
    return get_sqlalchemy().Index(*args, **kwargs)


def ForeignKey(*args, **kwargs):
    return get_sqlalchemy().ForeignKey(*args, **kwargs)


def relationship(*args, **kwargs):
    return get_sqlalchemy().orm.relationship(*args, **kwargs)


ORM_FIELD_TYPES = {
    "id": DatabaseIdType(),
    "int": DatabaseIntegerType(),
    "bool": DatabaseBooleanType(),
    "short_text": DatabaseTextType(length=HEAVEN_CM.get("ukf.text.short", 255)),
    "medium_text": DatabaseTextType(length=HEAVEN_CM.get("ukf.text.medium", 2047)),
    "long_text": DatabaseTextType(length=HEAVEN_CM.get("ukf.text.long", 65535)),
    "timestamp": DatabaseTimestampType(),
    "duration": DatabaseDurationType(),
    "json": DatabaseJsonType(),
    "tags": DatabaseNfType(
        nf_schema={
            "columns": ["slot", "value_"],
            "types": ["medium_text", "medium_text"],
            "indices": [
                {
                    "columns": ["ukf_id", "slot", "value_"],
                    "mysql_length": {"slot": 191, "value_": 191},
                },
                {
                    "columns": ["slot", "value_"],
                    "mysql_length": {"slot": 191, "value_": 191},
                },
            ],
        }
    ),
    "auths": DatabaseNfType(
        nf_schema={
            "columns": ["user_id", "authority"],
            "types": ["id", "short_text"],
            "indices": [
                ["ukf_id", "user_id", "authority"],
                ["ukf_id", "authority"],
                ["user_id", "authority"],
            ],
        }
    ),
    "synonyms": DatabaseNfType(
        nf_schema={
            "columns": ["synonyms"],
            "types": ["medium_text"],
            "indices": [
                {
                    "columns": ["ukf_id", "synonyms"],
                    "mysql_length": {"synonyms": 191},
                },
                {
                    "columns": ["synonyms"],
                    "mysql_length": {"synonyms": 191},
                },
            ],
        }
    ),
    "related": DatabaseNfType(
        nf_schema={
            "columns": ["subject_id", "relation", "object_id", "relation_id", "relation_resources"],
            "types": ["id", "medium_text", "id", "id", "json"],
            "indices": [
                {
                    "columns": ["ukf_id", "relation"],
                    "mysql_length": {"relation": 191},
                },
                {
                    "columns": ["subject_id", "object_id", "relation"],
                    "mysql_length": {"relation": 191},
                },
                {
                    "columns": ["relation", "subject_id", "object_id"],
                    "mysql_length": {"relation": 191},
                },
                {
                    "columns": ["relation", "object_id", "subject_id"],
                    "mysql_length": {"relation": 191},
                },
                ["relation_id"],
                ["object_id"],
            ],
        }
    ),
    "vector": DatabaseVectorType(),
}
ORM_VIRTUAL_FIELD_TYPES = {
    "id": "id",
    "expiration_timestamp": "timestamp",
}
_PRESERVED_FIELD_NAMES = {
    "metadata": "metadata_",  # SQLAlchemy reserved word
    "type": "type_",  # MySQL reserved word
    "owner": "owner_",  # MySQL reserved word
    "creator": "creator_",  # MySQL reserved word
    "value": "value_",  # Common name that may conflict
}
# Global caches for entity classes to prevent recreation
_ORM_ENTITY_CLASSES_CACHE = dict()


class ORMUKFDimEntityFactory:
    @classmethod
    def entity_class(cls, name: str, parent: str, nf_type: DatabaseNfType) -> Type[ExportableEntity]:
        super_cls = ExportableEntity
        cls_name = f"ORMUKFDimEntity_{name}"
        indices = nf_type.nf_schema.get("indices", list())
        attrs = {
            "__tablename__": name,
            "id": Column("id", DatabaseIdType(), primary_key=True, nullable=False),
            "ukf_id": Column("ukf_id", DatabaseIdType(), ForeignKey(f"{parent}.id"), nullable=False),
        }
        for field_name, field_type in zip(nf_type.nf_schema.get("columns"), nf_type.nf_schema.get("types")):
            alias_name = _PRESERVED_FIELD_NAMES.get(field_name, field_name)
            attrs[alias_name] = Column(alias_name, ORM_FIELD_TYPES.get(field_type), primary_key=False, nullable=True)
        attrs["__table_args__"] = tuple(
            [
                (
                    Index(f"idx_{name}_{'_'.join(idx['columns'])}", *idx["columns"], mysql_length=idx["mysql_length"])
                    if isinstance(idx, dict)
                    else Index(f"idx_{name}_{'_'.join(idx)}", *idx)
                )
                for idx in indices
            ]
        ) + ({"extend_existing": True},)

        def alias(cls, attr):
            return _PRESERVED_FIELD_NAMES.get(attr, attr)

        attrs["alias"] = classmethod(alias)
        return type(cls_name, (super_cls, get_base()), attrs)


class ORMUKFMainEntityFactory:
    indices = [
        {"columns": ["type_", "name", "version", "variant"], "mysql_length": {"name": 191}},
        ["type_", "workspace", "collection"],
        ["type_", "source", "creator_", "owner_"],
        ["creator_"],
        ["owner_"],
        ["type_", "priority"],
        ["timestamp"],
        ["type_", "timestamp"],
        ["last_verified"],
        ["type_", "last_verified"],
        ["expiration"],
        ["expiration_timestamp"],
    ]

    @classmethod
    def entity_class(cls, name: str, fields: List[str]) -> Type[ExportableEntity]:
        super_cls = ExportableEntity
        cls_name = f"ORMUKFMainEntity_{name}"
        attrs = {
            "__tablename__": name,
            "id": Column("id", DatabaseIdType(), primary_key=True, nullable=False),
        }
        ukf_schema = BaseUKF.schema()
        aliased_fields = set()
        for field_name in fields:
            if field_name == "id":
                continue  # Already handled above
            alias_name = _PRESERVED_FIELD_NAMES.get(field_name, field_name)
            if field_name in ORM_VIRTUAL_FIELD_TYPES:
                field_type = ORM_FIELD_TYPES.get(ORM_VIRTUAL_FIELD_TYPES[field_name])
            else:
                field_type = ORM_FIELD_TYPES.get(ukf_schema.get(field_name).name)
            attrs[alias_name] = Column(alias_name, field_type, nullable=True, primary_key=False)
            aliased_fields.add(alias_name)
        attrs["__table_args__"] = tuple(
            [
                (
                    Index(f"idx_{name}_{'_'.join(idx['columns'])}", *idx["columns"], mysql_length=idx["mysql_length"])
                    if isinstance(idx, dict)
                    else Index(f"idx_{name}_{'_'.join(idx)}", *idx)
                )
                for idx in cls.indices
                if set(idx["columns"] if isinstance(idx, dict) else idx).issubset(aliased_fields)
            ]
        ) + ({"extend_existing": True},)

        def alias(cls, attr):
            return _PRESERVED_FIELD_NAMES.get(attr, attr)

        attrs["alias"] = classmethod(alias)
        attrs["_dynamic_relationships"] = True
        return type(cls_name, (super_cls, get_base()), attrs)


class ORMUKFAdapter(BaseUKFAdapter):
    """\
    Simplified ORM adapter that only provides access to entity classes and conversion methods.

    This adapter creates SQLAlchemy ORM entities dynamically based on the included fields
    and provides conversion methods between UKF objects and ORM entities.
    """

    virtual_fields = tuple(ORM_VIRTUAL_FIELD_TYPES.keys())

    def __init__(self, *args, **kwargs):
        """\
        Initialize the ORM adapter with specified field inclusion.

        Args:
            name: Name of the adapter instance.
            include: List of BaseUKF field names to include in the ORM schema.
                If None, includes all available BaseUKF fields plus virtual fields.
                The 'id' field is always included automatically.
            exclude: List of BaseUKF field names to exclude from the ORM schema.
                If None, excludes no fields.
            *args: Additional positional arguments.
            **kwargs: Additional configuration parameters.

        Returns:
            None
        """
        super().__init__(*args, **kwargs)

        fields_signature = ",".join(sorted(self.fields))
        cache_key = f"{self.name}:{md5hash(fields_signature)}"
        if cache_key in _ORM_ENTITY_CLASSES_CACHE:
            self.dims = _ORM_ENTITY_CLASSES_CACHE[cache_key]
            self.main = self.dims["main"]
            return

        # Use cache_key hash for entity table names to ensure uniqueness
        name_hash = fmt_short_hash(md5hash(cache_key))
        self.main: type[ExportableEntity] = ORMUKFMainEntityFactory.entity_class(
            name=f"orm_{name_hash}_main",
            fields=self.fields,
        )
        self.dims = dict()
        ukf_schema = BaseUKF.schema()
        for field_name in self.fields:
            ukf_field_type = ukf_schema.get(field_name)
            if not ukf_field_type:
                continue
            field_type = ORM_FIELD_TYPES.get(ukf_field_type.name)
            if not isinstance(field_type, DatabaseNfType):
                continue
            self.dims[field_name] = ORMUKFDimEntityFactory.entity_class(
                name=f"orm_{name_hash}_dim_{field_name}",
                parent=f"orm_{name_hash}_main",
                nf_type=field_type,
            )
            rel_name = f"rel_{field_name}"
            setattr(
                self.main,
                rel_name,
                relationship(
                    self.dims[field_name],
                    primaryjoin=self.main.id == self.dims[field_name].ukf_id,
                    cascade="all, delete-orphan",
                ),
            )
        self.dims = {"main": self.main, **self.dims}  # Make sure main is always first
        _ORM_ENTITY_CLASSES_CACHE[cache_key] = self.dims

    def main_table_name(self) -> str:
        return self.main.__tablename__

    def dims_table_name(self, dim_name: str) -> str:
        dim_cls = self.dims.get(dim_name)
        if not dim_cls:
            raise ValueError(f"Dimension '{dim_name}' not found in adapter.")
        return dim_cls.__tablename__

    def table_names(self) -> List[str]:
        """Get all table names managed by this adapter."""
        return {dim: cls.__tablename__ for dim, cls in self.dims.items()}

    def _tags_from_ukf(self, kl: BaseUKF) -> ExportableEntity:
        return [
            self.dims["tags"](id=md5hash(d), **d)
            for d in [
                {
                    "ukf_id": kl.id,
                    "slot": slot,
                    "value_": value,
                }
                for slot, value in [tag_t(tag) for tag in kl.tags]
            ]
        ]

    def _synonyms_from_ukf(self, kl: BaseUKF) -> ExportableEntity:
        return [
            self.dims["synonyms"](id=md5hash(d), **d)
            for d in [
                {
                    "ukf_id": kl.id,
                    "synonyms": synonym,
                }
                for synonym in kl.synonyms
            ]
        ]

    def _auths_from_ukf(self, kl: BaseUKF) -> ExportableEntity:
        return [
            self.dims["auths"](id=md5hash(d), **d)
            for d in [
                {
                    "ukf_id": kl.id,
                    "user_id": user,
                    "authority": authority,
                }
                for user, authority in [tag_t(auth) for auth in kl.auths]
            ]
        ]

    def _related_from_ukf(self, kl: BaseUKF) -> ExportableEntity:
        return [
            self.dims["related"](id=md5hash(d), **d)
            for d in [
                {
                    "ukf_id": kl.id,
                    "subject_id": subject_id,
                    "relation": relation,
                    "object_id": object_id,
                    "relation_id": relation_id,
                    "relation_resources": relation_resources,
                }
                for subject_id, relation, object_id, relation_id, relation_resources in kl.related
            ]
        ]

    def _main_from_ukf(self, kl: BaseUKF) -> ExportableEntity:
        data = {_PRESERVED_FIELD_NAMES.get(k, k): getattr(kl, k) for k in self.fields if k not in self.virtual_fields}
        # Ad-hoc on the virtual_fields
        data["id"] = kl.id
        data["expiration_timestamp"] = kl.expiration_timestamp
        return self.main(**data)

    def from_ukf(self, ukf: BaseUKF) -> Dict[str, ExportableEntity]:
        """\
        Convert a BaseUKF object to a ORMUKFMainEntity object.

        Args:
            ukf: BaseUKF object to convert.

        Returns:
            A dictionary mapping table names to their corresponding ORM entity instances.
            `main` key corresponds to the main entity, and other keys correspond to dimension entities.
            The `main` will always be the first item in the dictionary.
        """
        return {dim_cls.__tablename__: getattr(self, f"_{field_name}_from_ukf")(ukf) for field_name, dim_cls in self.dims.items()}

    def entities(self, kls: Iterable[BaseUKF]) -> list[BaseUKF]:
        entities = [self.from_ukf(kl) for kl in kls]
        main_table_name = self.main.__tablename__
        main_entities = [entity.get(main_table_name) for entity in entities]
        dim_entities = [r for entity in entities for k, v in entity.items() if k != main_table_name for r in v]
        return main_entities + dim_entities

    def entity_mappings(self, kls: Iterable[BaseUKF]) -> Dict[str, List[Dict[str, Any]]]:
        """\
        Convert a list of BaseUKF objects to dictionary mappings for bulk insert.

        This method generates mappings suitable for SQLAlchemy's bulk_insert_mappings(),
        which is significantly more efficient than add_all() for large batches.

        Args:
            kls: Iterable of BaseUKF objects to convert.

        Returns:
            A dictionary mapping table names to lists of dictionaries.
            Each dictionary represents a row to be inserted.
            The 'main' table is always first, followed by dimension tables.
        """
        entities_dicts = [self.from_ukf(kl) for kl in kls]
        main_table_name = self.main.__tablename__

        # Build mappings for main table
        mappings = {main_table_name: []}
        for entity_dict in entities_dicts:
            main_entity = entity_dict.get(main_table_name)
            if main_entity:
                # Extract column values directly from the entity
                row_dict = {}
                for column in self.main.__table__.columns:
                    if hasattr(main_entity, column.key):
                        row_dict[column.key] = getattr(main_entity, column.key)
                mappings[main_table_name].append(row_dict)

        # Build mappings for dimension tables
        for field_name, dim_cls in self.dims.items():
            if field_name == "main":
                continue
            table_name = dim_cls.__tablename__
            mappings[table_name] = []
            for entity_dict in entities_dicts:
                dim_entities = entity_dict.get(table_name, [])
                for dim_entity in dim_entities:
                    # Extract column values directly from the entity
                    row_dict = {}
                    for column in dim_cls.__table__.columns:
                        if hasattr(dim_entity, column.key):
                            row_dict[column.key] = getattr(dim_entity, column.key)
                    mappings[table_name].append(row_dict)

        return mappings

    def to_ukf_data(self, entity: ExportableEntity) -> Dict[str, Any]:
        """\
        Convert a ORMUKFMainEntity object to a dictionary suitable for BaseUKF initialization.

        Args:
            entity: The ORM entity to convert.

        Returns:
            A dictionary of field names and values for BaseUKF initialization.
        """
        return {k: getattr(entity, _PRESERVED_FIELD_NAMES.get(k, k)) for k in self.fields if k not in self.virtual_fields}

    def from_result(self, result: SQLResponse) -> Dict[str, Any]:
        """\
        Convert a query result from the backend to the appropriate entity representation.

        Args:
            result: The raw result from a backend query.

        Returns:
            The converted entity representation.
        """
        raise NotImplementedError
