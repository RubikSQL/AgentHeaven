__all__ = [
    "TemplateUKFT",
]

from ...base import BaseUKF
from ...registry import register_ukft

from typing import ClassVar


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
