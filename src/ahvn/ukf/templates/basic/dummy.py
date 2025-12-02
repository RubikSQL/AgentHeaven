__all__ = [
    "DummyUKFT",
]

from ...base import BaseUKF
from ...registry import register_ukft

from typing import ClassVar


@register_ukft
class DummyUKFT(BaseUKF):
    """\
    Dummy knowledge entity for initialization purposes.

    UKF Type: dummy

    This UKFT is used internally for setting up vector database collections
    and should not be used for storing actual knowledge items.
    """

    type_default: ClassVar[str] = "dummy"
