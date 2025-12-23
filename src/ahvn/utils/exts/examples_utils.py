__all__ = [
    "ExampleType",
    "ExampleSource",
    "normalize_examples",
]

from typing import Iterable, Union, Dict, Any, Optional, Generator
from copy import deepcopy

from ...utils.basic.misc_utils import unique
from ...cache import CacheEntry
from ...ukf.templates.basic.experience import ExperienceUKFT
from ...klstore.base import BaseKLStore
from ...klengine.base import BaseKLEngine
from ...klengine.scan_engine import ScanKLEngine
from ...klbase.base import KLBase


ExampleType = Union[Dict[str, Any], CacheEntry, ExperienceUKFT]
ExampleSource = Union[Iterable[ExampleType], BaseKLStore, BaseKLEngine, KLBase]


def normalize_examples(
    examples: Optional[ExampleSource],
    search_args: Optional[Dict[str, Any]] = None,
) -> Generator[CacheEntry, None, None]:
    """\
    Normalize examples input to a generator of CacheEntry.

    Supported input types:
        1. None: Returns an empty generator
        2. Iterable[Union[Dict, CacheEntry, ExperienceUKFT]]:
            - Dict: Convert using CacheEntry.from_dict()
            - CacheEntry: Return directly
            - ExperienceUKFT: Convert using to_cache_entry() method
        3. BaseKLStore: Use ScanKLEngine to iterate all entries, convert ExperienceUKFT to CacheEntry
        4. BaseKLEngine: Use search() method to get results, extract 'kl' field, convert to CacheEntry if it's ExperienceUKFT
        5. KLBase: Use search() method to get results, extract 'kl' field, convert to CacheEntry if it's ExperienceUKFT

    Args:
        examples: Input examples, can be various types including: None, Iterable, KLStore, KLEngine, and KLBase
        search_args: Arguments passed to KLEngine.search() or KLBase.search() (only used when examples is a KLEngine or KLBase)

    Returns:
        Generator[CacheEntry, None, None]: A generator of CacheEntry, all entries will become Few-shot examples

    Examples:
        >>> # List of dictionaries
        >>> examples = [{"inputs": {"x": 1}, "output": 2}]
        >>> list(normalize_examples(examples))
        [CacheEntry(...)]

        >>> # List of ExperienceUKFT
        >>> exp = ExperienceUKFT.from_cache_entry(CacheEntry.from_args(x=1, output=2))
        >>> list(normalize_examples([exp]))
        [CacheEntry(...)]

        >>> # KLStore
        >>> from ahvn.klstore import CacheKLStore
        >>> store = CacheKLStore()
        >>> # ... add some ExperienceUKFT entries
        >>> list(normalize_examples(store))
        [CacheEntry(...), ...]

        >>> # KLEngine
        >>> from ahvn.klengine import ScanKLEngine
        >>> engine = ScanKLEngine(storage=store)
        >>> list(normalize_examples(engine, search_args={"topk": 5, "type": "experience"}))
        [CacheEntry(...), ...]

        >>> # KLBase
        >>> from ahvn.klbase import KLBase
        >>> klbase = KLBase(engines={"engine": engine})
        >>> klbase.set_default_engine("engine")
        >>> list(normalize_examples(klbase, search_args={"topk": 5, "type": "experience"}))
        [CacheEntry(...), ...]
    """
    if examples is None:
        yield from []
        return

    # If it's a KLStore, iterate all entries
    if isinstance(examples, BaseKLStore):
        engine = ScanKLEngine(storage=examples)
        yield from normalize_examples(engine, search_args=search_args)
        return

    # If it's a KLEngine or KLBase, use search method
    if isinstance(examples, BaseKLEngine) or isinstance(examples, KLBase):
        search_args = deepcopy(search_args) if search_args is not None else dict()
        yield from normalize_examples([r["kl"] for r in examples.search(**search_args | {"include": unique(["id", "kl"] + search_args.get("include", []))})])
        return

    yield from filter(
        lambda e: e is not None,
        [
            (
                example.to_cache_entry()
                if isinstance(example, ExperienceUKFT) or hasattr(example, "to_cache_entry")
                else example if isinstance(example, CacheEntry) else CacheEntry.from_dict(data=example) if isinstance(example, dict) else None
            )
            for example in examples
        ],
    )
    return
