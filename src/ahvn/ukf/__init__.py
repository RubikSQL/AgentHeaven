__all__ = [
    "default_trigger",
    "default_composer",
    "BaseUKF",
    "UKFTypeRegistry",
    "HEAVEN_UR",
    "register_ukft",
    "UKF_TYPES",
    "UKFIdType",
    "UKFIntegerType",
    "UKFBooleanType",
    "UKFShortTextType",
    "UKFMediumTextType",
    "UKFLongTextType",
    "UKFTimestampType",
    "UKFDurationType",
    "UKFJsonType",
    "UKFTagsType",
    "tag_s",
    "tag_v",
    "tag_t",
    "ptags",
    "gtags",
    "has_tag",
    "has_related",
    "next_ver",
    "DummyUKFT",
    "KnowledgeUKFT",
    "ExperienceUKFT",
    "ResourceUKFT",
    "DocumentUKFT",
    "TemplateUKFT",
    "PromptUKFT",
    "ToolUKFT",
    "templates",
]

from .ukf_utils import *

from .types import *

from .registry import *

from .base import *

import importlib


def __getattr__(name):
    if name in ("DummyUKFT", "KnowledgeUKFT", "ExperienceUKFT", "ResourceUKFT", "DocumentUKFT", "TemplateUKFT", "PromptUKFT", "ToolUKFT"):
        return getattr(importlib.import_module(".templates.basic", __name__), name)

    if name == "templates":
        return importlib.import_module(".templates", __name__)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
