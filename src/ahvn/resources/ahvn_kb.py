__all__ = [
    "HEAVEN_KB",
    "setup_heaven_kb",
]

from ahvn.utils.basic.config_utils import hpj
from ahvn.cache import JsonCache
from ahvn.klstore.cache_store import CacheKLStore
from ahvn.klengine.scan_engine import ScanKLEngine
from ahvn.klbase.base import KLBase


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


HEAVEN_KB = AhvnKLBase()
# # HEAVEN_STORES is a temporarily global store for AgentHeaven resources.
# # This will be replaced by a more robust resource management system (KLBase) in the future.
# # Currently, it only contains prompt UKFs used by various AgentHeaven components.
# HEAVEN_STORES = {
#     "prompts": CacheKLStore(name="prompts", cache=JsonCache(hpj("& ukfs/prompts"))),
# }


def setup_heaven_kb():
    HEAVEN_KB.clear()

    from ahvn.utils.exts.autotask import build_autotask_base_prompt
    from ahvn.utils.exts.autocode import build_autocode_base_prompt
    from ahvn.utils.exts.autofunc import build_autofunc_base_prompt

    autotask_prompt = build_autotask_base_prompt()
    autocode_prompt = build_autocode_base_prompt()
    autofunc_prompt = build_autofunc_base_prompt()
    HEAVEN_KB.batch_upsert(
        [autotask_prompt, autocode_prompt, autofunc_prompt],
        storages=["_prompts"],
    )


if __name__ == "__main__":
    setup_heaven_kb()

    # Debug
    for r in HEAVEN_KB.search(engine="prompts", name="autocode"):
        print(r["kl"].name)
    exit(0)
