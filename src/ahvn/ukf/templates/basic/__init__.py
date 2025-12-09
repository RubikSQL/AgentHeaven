import importlib


def __getattr__(name):
    if name == "DummyUKFT":
        return getattr(importlib.import_module(".dummy", __name__), name)

    if name == "KnowledgeUKFT":
        return getattr(importlib.import_module(".knowledge", __name__), name)

    if name == "ExperienceUKFT":
        return getattr(importlib.import_module(".experience", __name__), name)

    if name == "ResourceUKFT":
        return getattr(importlib.import_module(".resource", __name__), name)

    if name == "DocumentUKFT":
        return getattr(importlib.import_module(".document", __name__), name)

    if name == "TemplateUKFT":
        return getattr(importlib.import_module(".template", __name__), name)

    if name == "PromptUKFT":
        return getattr(importlib.import_module(".prompt", __name__), name)

    if name == "ToolUKFT":
        return getattr(importlib.import_module(".tool", __name__), name)

    if name == "tool":
        return importlib.import_module(".tool", __name__)

    # Also handle module imports if needed, e.g. ahvn.ukf.templates.basic.knowledge
    if name in ("knowledge", "experience", "resource", "document", "template", "prompt", "dummy"):
        return importlib.import_module(f".{name}", __name__)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
