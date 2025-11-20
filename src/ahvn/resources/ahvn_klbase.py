__all__ = [
    "AhvnKLBase",
    "HEAVEN_KB",
    "_rebuild_heaven_kb",
]
from ..utils.basic.log_utils import get_logger

logger = get_logger(__name__)

from ..utils.basic.config_utils import HEAVEN_CM, hpj
from ..utils.basic.file_utils import list_files, get_file_basename
from ..ukf.templates.basic.prompt import PromptUKFT
from ..ukf.ukf_utils import ptags
from ..klstore.db_store import DatabaseKLStore
from ..klengine.facet_engine import FacetKLEngine
from ..klengine.daac_engine import DAACKLEngine
from ..klbase.base import KLBase


class AhvnKLBase(KLBase):
    def __init__(self, name: str = "ahvn"):
        super().__init__(name=name)

        self.add_storage(
            name="ahvn-core",
            storage=DatabaseKLStore(
                name="ahvn-core",
                provider="sqlite",
                database=hpj("& ukfs/ahvn-core.db"),
                condition=lambda kl: kl.has_tag("AHVN", value="core"),
            ),
        )
        self.add_engine(
            name="ahvn-core-facet",
            engine=FacetKLEngine(
                name="ahvn-core-facet",
                storage=self.storages["ahvn-core"],
                inplace=True,
                condition=lambda kl: kl.has_tag("AHVN", value="core"),
            ),
        )

        self.add_storage(
            name="ahvn-i18n",
            storage=DatabaseKLStore(
                name="ahvn-i18n",
                provider="sqlite",
                database=hpj("& ukfs/ahvn-i18n/ahvn-i18n.db"),
                condition=lambda kl: kl.has_tag("AHVN", value="i18n"),
            ),
        )
        self.add_engine(
            name="ahvn-i18n-ac",
            engine=DAACKLEngine(
                name="ahvn-i18n-ac",
                storage=self.storages["ahvn-i18n"],
                encoder=lambda kl: kl.name.lower(),
                normalizer=True,
                path=hpj("& ukfs/ahvn-i18n/"),
                condition=lambda kl: kl.has_tag("AHVN", value="i18n"),
            ),
        )


try:
    HEAVEN_KB = AhvnKLBase()
except Exception:
    logger.info(
        "Failed to initialize HEAVEN_KB. This is normal if you are running `setup` for the first time. Please make sure the config is setup and restart the program."
    )
    HEAVEN_KB = None


def _build_system_prompts():
    prompts = list()
    for file in list_files("& prompts/system/", ext="jinja;jinja2;j2;txt", abs=False):
        for lang in HEAVEN_CM.get("prompts.langs", list()):
            file_name = get_file_basename(file, ext=False)
            prompts.append(
                PromptUKFT.from_path(
                    path="& prompts/system/",
                    entry=file,
                    name=f"system/{file_name}",
                    keep_path=False,
                    lang=lang,
                    tags=ptags(AHVN="core", BUILTIN=True),
                ).signed(
                    system=True,
                    verified=True,
                    workspace="ahvn-core",
                )
            )
    HEAVEN_KB.batch_upsert(prompts)


def _build_translator_knowledge():
    pass


def _rebuild_heaven_kb():
    HEAVEN_KB.clear()
    # System Prompts
    _build_system_prompts()
    # Translator Knowledges
    _build_translator_knowledge()
