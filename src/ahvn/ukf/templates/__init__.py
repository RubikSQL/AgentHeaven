from ahvn.utils.basic import lazy_getattr, lazy_import_submodules

_EXPORT_MAP = {
    "DummyUKFT": ".basic",
    "KnowledgeUKFT": ".basic",
    "ExperienceUKFT": ".basic",
    "ResourceUKFT": ".basic",
    "DocumentUKFT": ".basic",
    "TemplateUKFT": ".basic",
    "PromptUKFT": ".basic",
    "ToolUKFT": ".basic",
}

_SUBMODULES = ["basic"]


def __getattr__(name):
    mod = lazy_import_submodules(name, _SUBMODULES, __name__)
    if mod:
        return mod
    return lazy_getattr(name, _EXPORT_MAP, __name__)
