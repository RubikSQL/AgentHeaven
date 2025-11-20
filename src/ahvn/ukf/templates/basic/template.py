__all__ = [
    "TemplateUKFT",
]

from ...types import UKFShortTextType
from ...base import BaseUKF, ptags
from ...registry import register_ukft

from typing import Set
from pydantic import Field, field_validator


# TODO
@register_ukft
class TemplateUKFT(BaseUKF):
    """\
    Template like jinja folders or other templating systems.

    UKF Type: template
    Recommended Components of `content_resources`:
        None

    Recommended Composers:
        Any
    """

    type: UKFShortTextType = Field(
        default="template",
        description=(
            "Knowledge category for routing and processing. For example: 'experience', 'knowledge', 'resource'. "
            "A major classifier used by systems to handle different knowledge types appropriately. Typically have different classes and `content_composers`."
        ),
        frozen=True,
    )

    @field_validator("tags", mode="after")
    @classmethod
    def _ukf_template_type_tag(cls, tags: Set[str]) -> Set[str]:
        return tags.union(ptags(UKF_TYPE="template"))
