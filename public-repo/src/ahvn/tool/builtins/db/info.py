from ....utils.db import Database
from ....klbase import KLBase
from ....ukf import BaseUKF, EnumUKFT, ColumnUKFT, TableUKFT, DatabaseUKFT
from ....utils.klop import KLOp

from typing import List, Optional


def db_info(kb: KLBase, engine: str, db_id: str) -> str:
    pass
    # db_kl = kb.search(
    #     engine=engine,
    #     type=DatabaseUKFT.type,
    #     tags=KLOp.NF(slot="DATABASE", value=db_id),
    # )
    # tab_kls = kb.search(
    #     engine=engine,
    #     type=TableUKFT.type,
    #     tags=KLOp.NF(slot="DATABASE", value=db_id),
    # )
    # return db_kl.text(composer="default")
