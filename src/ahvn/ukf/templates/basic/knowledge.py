__all__ = [
    "KnowledgeUKFT",
]

from ...types import UKFShortTextType
from ...base import BaseUKF, ptags
from ...registry import register_ukft

from typing import Set, ClassVar
from pydantic import Field, field_validator


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
