__all__ = [
    "DocumentUKFT",
]

from ...types import UKFShortTextType
from ...base import BaseUKF, ptags
from ...registry import register_ukft

from pydantic import Field, field_validator
from typing import Set, ClassVar


@register_ukft
class DocumentUKFT(BaseUKF):
    """\
    Document (chunks) entity for storing text-based information.

    UKF Type: document
    Recommended Components of `content_resources`:
        None

    Recommended Composers:
        Any
    """

    type_default: ClassVar[str] = "document"
