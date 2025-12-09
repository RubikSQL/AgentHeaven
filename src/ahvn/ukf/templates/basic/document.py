__all__ = [
    "DocumentUKFT",
]

from ...base import BaseUKF
from ...registry import register_ukft

from typing import ClassVar


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
