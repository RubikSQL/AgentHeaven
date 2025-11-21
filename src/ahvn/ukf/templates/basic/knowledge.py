__all__ = [
    "KnowledgeUKFT",
]

from ...types import UKFShortTextType
from ...base import BaseUKF, ptags
from ...registry import register_ukft

from typing import Set
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

    type: UKFShortTextType = Field(
        default="knowledge",
        description=(
            "Knowledge category for routing and processing. For example: 'experience', 'knowledge', 'resource'. "
            "A major classifier used by systems to handle different knowledge types appropriately. Typically have different classes and `content_composers`."
        ),
        frozen=True,
    )

    @field_validator("tags", mode="before")
    @classmethod
    def _ukf_knowledge_type_tag(cls, tags) -> Set[str]:
        # Convert to set if it's a list (from JSON deserialization)
        if isinstance(tags, list):
            tags = set(tags)
        elif not isinstance(tags, set):
            tags = set() if tags is None else {tags} if isinstance(tags, str) else set(tags)
        return tags.union(ptags(UKF_TYPE="knowledge"))
