__all__ = [
    "TemplateUKFT",
]

from ...types import UKFShortTextType
from ...base import BaseUKF, ptags
from ...registry import register_ukft

from typing import Set, ClassVar
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

    type_default: ClassVar[str] = "template"
