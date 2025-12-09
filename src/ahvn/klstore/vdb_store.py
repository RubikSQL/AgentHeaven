from __future__ import annotations

__all__ = [
    "VectorKLStore",
]

from typing import Any, Generator, Iterable, List, Optional, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from llama_index.core.schema import TextNode

from ..adapter.vdb import VdbUKFAdapter
from ..ukf.base import BaseUKF
from ..utils.basic.config_utils import HEAVEN_CM
from ..utils.basic.log_utils import get_logger
from ..utils.basic.misc_utils import unique
from ..utils.basic.progress_utils import Progress
from ..utils.vdb.base import VectorDatabase
from .base import BaseKLStore

logger = get_logger(__name__)


class VectorKLStore(BaseKLStore):
    """\
    Vector database backed KL store using the VDB adapter.

    Minimal implementation that maps vector database records to BaseUKF objects.
    """

    def __init__(self, collection: Optional[str] = None, name: Optional[str] = None, condition: Optional[Callable] = None, *args, **kwargs):
        """\
        Initialize the vector database KL store.

        Args:
            collection: Vector database collection or table name.
            name: Name of the KLStore instance. If None, defaults to the collection name or "default".
            condition: Optional upsert/insert condition to apply to the KLStore.
                KLs that do not satisfy the condition will be ignored. If None, all KLs are accepted.
            *args: Additional positional arguments for BaseKLStore.
            **kwargs: Additional keyword arguments for adapter or vector database configuration.
        """
        super().__init__(name=name or collection, condition=condition, *args, **kwargs)
        provider = kwargs.get("provider") or HEAVEN_CM.get("vdb.default_provider", "lancedb")
        encoder = kwargs.get("encoder")
        embedder = kwargs.get("embedder")
        include = kwargs.get("include")
        exclude = kwargs.get("exclude")
        collection = collection or kwargs.get("collection") or HEAVEN_CM.get(f"vdb.providers.{provider}.collection")
        connection_args = {
            k: v
            for k, v in kwargs.items()
            if k
            not in {
                "collection",
                "provider",
                "encoder",
                "embedder",
                "include",
                "exclude",
            }
        }

        self.vdb = VectorDatabase(collection=collection or self.name, provider=provider, encoder=encoder, embedder=embedder, **connection_args)

        adapter_kwargs = {
            "backend": self.vdb.backend,
            "name": self.name,
            "include": include,
            "exclude": exclude,
        }
        self.adapter = VdbUKFAdapter(**adapter_kwargs)
        self._init()

    def _init(self):
        self.vdb.connect()
        # Insert a dummy record to specify the schema
        dummy = BaseUKF(name="__dummy__", type="dummy")
        self.vdb.vdb.add(self._batch_convert([dummy]))
        self.vdb.flush()
        # Remove the dummy node
        self._remove(dummy.id)

    def _has(self, key: int) -> bool:
        ukf_id = self.adapter.parse_id(key)
        entities = self.vdb.vdb.get_nodes(node_ids=[ukf_id])
        if len(entities) > 1:
            raise ValueError(f"Multiple entities found for key {key} (id: {ukf_id})")
        return len(entities) == 1

    def _get(self, key: int, default: Any = ...) -> Optional[BaseUKF]:
        ukf_id = self.adapter.parse_id(key)
        entities = self.vdb.vdb.get_nodes(node_ids=[ukf_id])
        if len(entities) > 1:
            raise ValueError(f"Multiple entities found for key {key} (id: {ukf_id})")
        if len(entities) < 1:
            return default
        return self.adapter.to_ukf(entity=entities[0])

    def _batch_convert(self, kls: Iterable[BaseUKF]) -> List[TextNode]:
        nodes = list()
        keys_embeddings = self.vdb.batch_k_encode_embed(kls)
        for kl, (key, embedding) in zip(kls, keys_embeddings):
            nodes.append(self.adapter.from_ukf(kl=kl, key=key, embedding=embedding))
        return nodes

    def _upsert(self, kl: BaseUKF, **kwargs):
        ukf_id = self.adapter.parse_id(kl.id)
        self.vdb.vdb.delete_nodes([ukf_id])
        self.vdb.vdb.add(self._batch_convert([kl]))

    def _batch_upsert(self, kls: list[BaseUKF], progress: Progress = None, **kwargs):
        kls = unique(kls, key=lambda kl: kl.id)  # Keeping only the first occurrence of each ID in case of duplicates
        if not kls:
            return
        ukf_ids = [self.adapter.parse_id(kl.id) for kl in kls]
        self.vdb.vdb.delete_nodes(ukf_ids)
        self.vdb.vdb.add(self._batch_convert(kls))
        if progress is not None:
            progress.update(len(kls))

    def _batch_insert(self, kls: list[BaseUKF], progress: Progress = None, **kwargs):
        kls = unique(kls, key=lambda kl: kl.id)  # Keeping only the first occurrence of each ID in case of duplicates
        if not kls:
            return
        ukf_ids = [self.adapter.parse_id(kl.id) for kl in kls]
        existing = set(node.node_id for node in self.vdb.vdb.get_nodes(node_ids=ukf_ids))
        delta = [kl for kl, ukf_id in zip(kls, ukf_ids) if ukf_id not in existing]
        if not delta:
            return
        self.vdb.vdb.add(self._batch_convert(delta))
        if progress is not None:
            progress.update(len(delta))

    def _remove(self, key: int, **kwargs) -> bool:
        if key not in self:
            return False
        self.vdb.vdb.delete_nodes([self.adapter.parse_id(key)])
        return True

    def _batch_remove(self, keys: Iterable[int], progress: Progress = None, **kwargs):
        keys = unique(keys)  # Keeping only unique keys
        if not keys:
            return
        ukf_ids = [self.adapter.parse_id(key) for key in keys if key in self]
        if not ukf_ids:
            return
        self.vdb.vdb.delete_nodes(ukf_ids)
        if progress is not None:
            progress.update(len(ukf_ids))

    def __len__(self) -> int:
        return len(self.vdb._get_all_nodes())

    def _itervalues(self) -> Generator[BaseUKF, None, None]:
        for node in self.vdb._get_all_nodes():
            yield self.adapter.to_ukf(entity=node)

    def _clear(self):
        self.vdb.clear()

    def close(self):
        if self.vdb is not None:
            self.vdb.close()
        self.vdb = None
