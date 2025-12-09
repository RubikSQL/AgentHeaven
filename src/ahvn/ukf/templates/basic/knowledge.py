__all__ = [
    "KnowledgeUKFT",
]

from ...base import BaseUKF
from ...registry import register_ukft

from typing import ClassVar


@register_ukft
class KnowledgeUKFT(BaseUKF):
    """\
    General-purpose knowledge entity for storing diverse information types.

    UKF Type: knowledge
    Recommended Components of `content_resources`:
        None

    Recommended Composers:
        Any
    """

    type_default: ClassVar[str] = "knowledge"
