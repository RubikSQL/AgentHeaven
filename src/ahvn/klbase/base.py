__all__ = [
    "KLBase",
]


from ..ukf.base import BaseUKF

from ..klstore import BaseKLStore

from ..klengine import BaseKLEngine

from ..tool import ToolRegistry

from ..utils.basic.log_utils import get_logger
from ..utils.basic.progress_utils import Progress, NoProgress

logger = get_logger(__name__)


from typing import Optional, Union, List, Dict, Any, Iterable, Tuple, Type


class KLBase(ToolRegistry):
    def __init__(
        self,
        storages: Optional[Union[List[BaseKLStore], Dict[str, BaseKLStore]]] = None,
        engines: Optional[Union[List[BaseKLEngine], Dict[str, BaseKLEngine]]] = None,
        name: Optional[str] = None,
        *args,
        **kwargs,
    ):
        """\
        Initialization.

        Args:
            storages (Union[List[BaseKLStore], Dict[BaseKLStore]], optional):
                A list or dictionary of storage backends. Defaults to None.
            engines (Union[List[BaseKLEngine], Dict[BaseKLEngine]], optional):
                A list or dictionary of engine backends. Defaults to None.
            name (Optional[str], optional):
                The name of this KLBase instance. If None, defaults to "default".
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.
        """
        super().__init__()
        self.name = name or "default"
        self.desync = set()

        if storages is None:
            self.storages = dict()
        elif isinstance(storages, list):
            self.storages = {s.name: s for s in storages}
        elif isinstance(storages, dict):
            self.storages = storages

        if engines is None:
            self.engines = dict()
        elif isinstance(engines, list):
            self.engines = {e.name: e for e in engines}
        elif isinstance(engines, dict):
            self.engines = engines

        self.default_engine = None

    def add_storage(self, storage: BaseKLStore, name: Optional[str] = None):
        """\
        Add a storage backend.

        Args:
            storage (BaseKLStore):
                The storage backend to add.
            name (Optional[str], optional):
                The name to register the storage under. If None, uses storage.name. Defaults to None
        """
        self.storages[name or storage.name] = storage

    def del_storage(self, name: str):
        """\
        Delete a storage backend.

        Args:
            name (str):
                The name of the storage backend to delete.
        """
        if name in self.storages:
            del self.storages[name]

    def add_engine(self, engine: BaseKLEngine, name: Optional[str] = None, desync: bool = False):
        """\
        Add an engine backend.

        Args:
            engine (BaseKLEngine):
                The engine backend to add.
            name (Optional[str], optional):
                The name to register the engine under. If None, uses engine.name. Defaults to None.
            desync (bool, optional):
                Whether to desynchronize the engine upon addition. Defaults to False.
        """
        self.engines[name or engine.name] = engine
        if desync:
            self.desync.add(name or engine.name)

    def del_engine(self, name: str):
        """\
        Delete an engine backend.

        Args:
            name (str):
                The name of the engine backend to delete.
        """
        if name in self.engines:
            del self.engines[name]

    def desync_engine(self, name: str):
        """\
        Desynchronize an engine backend.

        Args:
            name (str):
                The name of the engine backend to desynchronize.
        """
        self.desync.add(name)

    def resync_engine(self, name: str):
        """\
        Synchronize an engine backend.

        Args:
            name (str):
                The name of the engine backend to synchronize.
        """
        if name in self.desync:
            self.desync.remove(name)
            self.engines[name].sync()

    def upsert(self, kl: BaseUKF, storages: List[str] = None, engines: List[str] = None, **kwargs):
        """\
        Upsert a KL into all storages and engines.

        Args:
            kl (BaseUKF):
                The KL to upsert.
            storages (List[str], optional):
                The list of storage names to upsert into.
                If None and engines is None/empty, upserts into all storages. Defaults to None.
                If None and engines is not None/empty, upserts into no storages.
            engines (List[str], optional):
                The list of engine names to upsert into.
                If None and storages is None/empty, upserts into all engines. Defaults to None.
                If None and storages is not None/empty, upserts into no engines.
            **kwargs: Additional keyword arguments.
        """
        if (storages is None) and (engines is None):
            storages = list(self.storages.keys())
            engines = list(self.engines.keys())
        elif storages is None:
            storages = list() if engines else list(self.storages.keys())
        elif engines is None:
            engines = list() if storages else list(self.engines.keys())
        for sname in storages:
            if sname in self.storages:
                self.storages[sname].upsert(kl, **kwargs)
        for ename in engines:
            if ename in self.engines:
                if ename in self.desync:
                    continue
                self.engines[ename].upsert(kl, **kwargs)

    def insert(self, kl: BaseUKF, storages: List[str] = None, engines: List[str] = None, **kwargs):
        """\
        Insert a KL into all storages and engines.

        Args:
            kl (BaseUKF):
                The KL to insert.
            storages (List[str], optional):
                The list of storage names to insert into.
                If None and engines is None/empty, inserts into all storages. Defaults to None.
                If None and engines is not None/empty, inserts into no storages.
            engines (List[str], optional):
                The list of engine names to insert into.
                If None and storages is None/empty, inserts into all engines. Defaults to None.
                If None and storages is not None/empty, inserts into no engines.
            **kwargs: Additional keyword arguments.
        """
        if (storages is None) and (engines is None):
            storages = list(self.storages.keys())
            engines = list(self.engines.keys())
        elif storages is None:
            storages = list() if engines else list(self.storages.keys())
        elif engines is None:
            engines = list() if storages else list(self.engines.keys())
        for sname in storages:
            if sname in self.storages:
                self.storages[sname].insert(kl, **kwargs)
        for ename in engines:
            if ename in self.engines:
                if ename in self.desync:
                    continue
                self.engines[ename].insert(kl, **kwargs)

    def batch_upsert(self, kls: List[BaseUKF], storages: List[str] = None, engines: List[str] = None, progress: Type[Progress] = None, **kwargs):
        """\
        Batch upsert KLs into all storages and engines.

        Args:
            kls (List[BaseUKF]):
                The list of KLs to upsert.
            storages (List[str], optional):
                The list of storage names to upsert into.
                If None and engines is None/empty, batch upserts into all storages. Defaults to None.
                If None and engines is not None/empty, batch upserts into no storages.
            engines (List[str], optional):
                The list of engine names to upsert into. If None, batch upserts into all engines. Defaults to None.
                If None and storages is None/empty, batch upserts into all engines.
                If None and storages is not None/empty, batch upserts into no engines.
            **kwargs: Additional keyword arguments.
        """
        if (storages is None) and (engines is None):
            storages = list(self.storages.keys())
            engines = list(self.engines.keys())
        elif storages is None:
            storages = list() if engines else list(self.storages.keys())
        elif engines is None:
            engines = list() if storages else list(self.engines.keys())
        target_engines = [ename for ename in engines if (ename in self.engines) and (ename not in self.desync)]
        total = len(kls) * (len([s for s in storages if s in self.storages]) + len(target_engines))
        progress_cls = progress or NoProgress
        with progress_cls(total=total, desc=f"Batch upserting KLBase '{self.name}'") as pbar:
            for sname in storages:
                if sname in self.storages:
                    self.storages[sname].batch_upsert(kls, progress=None, **kwargs)
                    pbar.update(len(kls))
            for ename in target_engines:
                self.engines[ename].batch_upsert(kls, progress=None, **kwargs)
                pbar.update(len(kls))

    def batch_insert(self, kls: List[BaseUKF], storages: List[str] = None, engines: List[str] = None, progress: Type[Progress] = None, **kwargs):
        """\
        Batch insert KLs into all storages and engines.

        Args:
            kls (List[BaseUKF]):
                The list of KLs to insert.
            storages (List[str], optional):
                The list of storage names to insert into.
                If None and engines is None/empty, batch inserts into all storages. Defaults to None.
                If None and engines is not None/empty, batch inserts into no storages.
            engines (List[str], optional):
                The list of engine names to insert into.
                If None and storages is None/empty, batch inserts into all engines. Defaults to None.
                If None and storages is not None/empty, batch inserts into no engines.
            **kwargs: Additional keyword arguments.
        """
        if (storages is None) and (engines is None):
            storages = list(self.storages.keys())
            engines = list(self.engines.keys())
        elif storages is None:
            storages = list() if engines else list(self.storages.keys())
        elif engines is None:
            engines = list() if storages else list(self.engines.keys())
        target_engines = [ename for ename in engines if (ename in self.engines) and (ename not in self.desync)]
        total = len(kls) * (len([s for s in storages if s in self.storages]) + len(target_engines))
        progress_cls = progress or NoProgress
        with progress_cls(total=total, desc=f"Batch inserting KLBase '{self.name}'") as pbar:
            for sname in storages:
                if sname in self.storages:
                    self.storages[sname].batch_insert(kls, progress=None, **kwargs)
                    pbar.update(len(kls))
            for ename in target_engines:
                self.engines[ename].batch_insert(kls, progress=None, **kwargs)
                pbar.update(len(kls))

    def remove(self, key: Union[int, str, BaseUKF], storages: List[str] = None, engines: List[str] = None, **kwargs):
        """\
        Remove a KL from all storages and engines.

        Args:
            key (Union[int, str, BaseUKF]):
                The key or BaseUKF instance of the KL to remove.
            storages (List[str], optional):
                The list of storage names to remove from.
                If None and engines is None/empty, removes from all storages. Defaults to None.
                If None and engines is not None/empty, removes from no storages.
            engines (List[str], optional):
                The list of engine names to remove from.
                If None and storages is None/empty, removes from all engines. Defaults to None.
                If None and storages is not None/empty, removes from no engines.
            **kwargs: Additional keyword arguments.
        """
        if (storages is None) and (engines is None):
            storages = list(self.storages.keys())
            engines = list(self.engines.keys())
        elif storages is None:
            storages = list() if engines else list(self.storages.keys())
        elif engines is None:
            engines = list() if storages else list(self.engines.keys())
        for sname in storages:
            if sname in self.storages:
                self.storages[sname].remove(key, **kwargs)
        for ename in engines:
            if ename in self.engines:
                if ename in self.desync:
                    continue
                self.engines[ename].remove(key, **kwargs)

    def batch_remove(
        self, keys: List[Union[int, str, BaseUKF]], storages: List[str] = None, engines: List[str] = None, progress: Type[Progress] = None, **kwargs
    ):
        """\
        Batch remove KLs from all storages and engines.

        Args:
            keys (List[Union[int, str, BaseUKF]]):
                The list of keys or BaseUKF instances of the KLs to remove.
            storages (List[str], optional):
                The list of storage names to remove from.
                If None and engines is None/empty, batch removes from all storages. Defaults to None.
                If None and engines is not None/empty, batch removes from no storages.
            engines (List[str], optional):
                The list of engine names to remove from.
                If None and storages is None/empty, batch removes from all engines. Defaults to None.
                If None and storages is not None/empty, batch removes from no engines.
            **kwargs: Additional keyword arguments.
        """
        if (storages is None) and (engines is None):
            storages = list(self.storages.keys())
            engines = list(self.engines.keys())
        elif storages is None:
            storages = list() if engines else list(self.storages.keys())
        elif engines is None:
            engines = list() if storages else list(self.engines.keys())
        target_engines = [ename for ename in engines if (ename in self.engines) and (ename not in self.desync)]
        total = len(keys) * (len([s for s in storages if s in self.storages]) + len(target_engines))
        progress_cls = progress or NoProgress
        with progress_cls(total=total, desc=f"Batch removing KLBase '{self.name}'") as pbar:
            for sname in storages:
                if sname in self.storages:
                    self.storages[sname].batch_remove(keys, progress=None, **kwargs)
                    pbar.update(len(keys))
            for ename in target_engines:
                self.engines[ename].batch_remove(keys, progress=None, **kwargs)
                pbar.update(len(keys))

    def clear(self, storages: List[str] = None, engines: List[str] = None):
        """\
        Clear all KLs from all storages and engines.

        Args:
            storages (List[str], optional):
                The list of storage names to clear.
                If None and engines is None/empty, clears all storages. Defaults to None.
                If None and engines is not None/empty, clears no storages.
            engines (List[str], optional):
                The list of engine names to clear.
                If None and storages is None/empty, clears all engines. Defaults to None.
                If None and storages is not None/empty, clears no engines.
        """
        if (storages is None) and (engines is None):
            storages = list(self.storages.keys())
            engines = list(self.engines.keys())
        elif storages is None:
            storages = list() if engines else list(self.storages.keys())
        elif engines is None:
            engines = list() if storages else list(self.engines.keys())
        for sname in storages:
            if sname in self.storages:
                self.storages[sname].clear()
        for ename in engines:
            if ename in self.engines:
                if ename in self.desync:
                    continue
                self.engines[ename].clear()

    def set_default_engine(self, name: str):
        """\
        Set the default engine for searches.

        Args:
            name (str):
                The name of the engine to set as default.
        """
        if name not in self.engines:
            raise ValueError(f"Engine '{name}' not found in KLBase.")
        self.default_engine = name

    def search(self, engine: Optional[str] = None, *args, **kwargs) -> Iterable[Dict[str, Any]]:
        """\
        Search for KLs using a specified engine.

        Args:
            engine (Optional[str]):
                The name of the engine to use for searching. If None, uses the default engine.
                If no default engine is set, raises a ValueError. Defaults to None.
            *args: Additional positional arguments for the engine's search method.
            **kwargs: Additional keyword arguments for the engine's search method.

        Returns:
            Iterable[Dict[str, Any]]: A list of dictionary, each being one search result.
                As a recommended convention, all engine searches should support at least these keys:
                    - "id" (int): the identifier of the KL.
                    - "kl" (BaseUKF): the KL instance, if the engine is `recoverable`.
                Other keys can be added as needed, which are usually search-specific (e.g., vector search score).
        """
        if engine is None:
            if self.default_engine is None:
                raise ValueError("No default engine set for KLBase.")
            if self.default_engine not in self.engines:
                raise ValueError(f"Default engine '{self.default_engine}' not found in KLBase.")
            engine = self.default_engine
        if engine not in self.engines:
            raise ValueError(f"Engine '{engine}' not found in KLBase.")
        return self.engines[engine].search(*args, **kwargs)

    def list_search(self) -> List[Tuple[str, Optional[str]]]:
        """\
        List all available engine search methods.

        Returns:
            List[Tuple[str, Optional[str]]]: A list of search method names, each a Tuple:
                The first string is the engine to call.
                The second (optional) string is the engine's search mode.
        """
        return [(engine_name, search_mode) for engine_name, engine in self.engines.items() for search_mode in engine.list_search()]

    def sync(self, include_desynced: bool = False, progress: Type[Progress] = None, **kwargs):
        """
        Sync all engines (one-time operation).

        Args:
            include_desynced (bool): Whether to sync desynced engines as well. Default is False.
            progress (Type[Progress]): Progress class for reporting. None for silent, TqdmProgress for terminal.
            **kwargs: Additional keyword arguments for the engine's sync method.
        """
        for engine in self.engines.values():
            if (engine.name in self.desync) and (not include_desynced):
                continue
            engine.sync(progress=progress, **kwargs)

    def sync_desynced(self, progress: Type[Progress] = None, **kwargs):
        """
        Sync all desynced engines (one-time operation).

        Args:
            progress (Type[Progress]): Progress class for reporting. None for silent, TqdmProgress for terminal.
            **kwargs: Additional keyword arguments for the engine's sync method.
        """
        for ename in self.desync:
            if ename in self.engines:
                self.engines[ename].sync(progress=progress, **kwargs)

    def flush(self):
        """\
        Flush all storages and engines.
        """
        for storage in self.storages.values():
            if hasattr(storage, "flush"):
                storage.flush()
        for engine in self.engines.values():
            if hasattr(engine, "flush"):
                engine.flush()

    def close(self):
        """\
        Close all storages and engines.
        """
        for engine in self.engines.values():
            if hasattr(engine, "close"):
                engine.close()
        self.engines = dict()
        for storage in self.storages.values():
            if hasattr(storage, "close"):
                storage.close()
        self.storages = dict()
