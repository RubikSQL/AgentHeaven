__all__ = [
    "HEAVEN_KB",
    "setup_heaven_kb",
]

from ahvn.cache import JsonCache
from ahvn.klstore.cache_store import CacheKLStore
from ahvn.klengine.scan_engine import ScanKLEngine
from ahvn.klbase.base import KLBase
from ahvn.ukf.templates.basic.prompt import PromptUKFT

from ahvn.utils.basic.config_utils import hpj, HEAVEN_CM
from ahvn.utils.basic.log_utils import get_logger

logger = get_logger(__name__)


class AhvnKLBase(KLBase):
    def __init__(self):
        super().__init__(name="ahvn")
        self.add_storage(
            CacheKLStore(
                name="_prompts",
                cache=JsonCache(hpj("& ukfs/prompts")),
            )
        )
        self.add_engine(
            ScanKLEngine(
                name="prompts",
                storage=self.storages["_prompts"],
            )
        )

    def get_prompt(self, name: str, **kwargs) -> PromptUKFT:
        results = self.search(engine="prompts", name=name, **kwargs)
        if not results:
            raise ValueError(f"Prompt '{name}' not found in HEAVEN_KB.")
        if len(results) > 1:
            raise ValueError(f"Multiple prompts named '{name}' found in HEAVEN_KB. Please refine your search facets by adding `**kwargs`.")
        return results[0]["kl"]


HEAVEN_KB = AhvnKLBase()


def setup_heaven_kb():
    logger.info("Re-generating HEAVEN_KB...")
    HEAVEN_KB.clear()

    from ahvn.utils.exts.autotask import build_autotask_base_prompt
    from ahvn.utils.exts.autocode import build_autocode_base_prompt
    from ahvn.utils.exts.autofunc import build_autofunc_base_prompt

    base_prompt = PromptUKFT.from_path(
        "& prompts/system",
        default_entry="prompt.jinja",
        name="prompt",
    )
    autotask_base_prompt = build_autotask_base_prompt(output_schema=None)
    autotask_text_prompt = build_autotask_base_prompt(output_schema={"mode": "base"})
    autotask_repr_prompt = build_autotask_base_prompt(output_schema={"mode": "repr"})
    autotask_json_prompt = build_autotask_base_prompt(output_schema={"mode": "json", "args": {"indent": 4}})
    autotask_code_prompt = build_autotask_base_prompt(output_schema={"mode": "code"})
    autocode_prompt = build_autocode_base_prompt()
    autofunc_prompt = build_autofunc_base_prompt()
    HEAVEN_KB.batch_upsert(
        [
            base_prompt,
            autotask_base_prompt,
            autotask_text_prompt,
            autotask_repr_prompt,
            autotask_json_prompt,
            autotask_code_prompt,
            autocode_prompt,
            autofunc_prompt,
        ],
        storages=["_prompts"],
    )


# Temporary trigger for initial setup
if (len(HEAVEN_KB.storages["_prompts"]) == 0) or (HEAVEN_CM.get("core.debug")):
    setup_heaven_kb()


if __name__ == "__main__":
    setup_heaven_kb()

    # Debug
    for r in HEAVEN_KB.search(engine="prompts", name="autocode"):
        print(r["kl"].name)
    exit(0)
