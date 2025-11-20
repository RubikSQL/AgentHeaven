__all__ = [
    "DocumentUKFT",
]

from ...types import UKFShortTextType
from ...base import BaseUKF, ptags
from ...registry import register_ukft

from pydantic import Field, field_validator
from typing import Set


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

    type: UKFShortTextType = Field(
        default="document",
        description=(
            "Knowledge category for routing and processing. For example: 'experience', 'knowledge', 'resource'. "
            "A major classifier used by systems to handle different knowledge types appropriately. Typically have different classes and `content_composers`."
        ),
        frozen=True,
    )

    @field_validator("tags", mode="after")
    @classmethod
    def _ukf_document_type_tag(cls, tags) -> Set[str]:
        # Convert to set if it's a list (from JSON deserialization)
        if isinstance(tags, list):
            tags = set(tags)
        elif not isinstance(tags, set):
            tags = set() if tags is None else {tags} if isinstance(tags, str) else set(tags)
        return tags.union(ptags(UKF_TYPE="document"))
