"""\
Common prompt builder utilities for AgentHeaven.

This module provides the `_build_prompt` function that is used by
build_autotask_prompt, build_autofunc_prompt, and build_autocode_prompt
to create PromptUKFT instances.
"""

from typing import List, Optional

from ...ukf.templates.basic.prompt import PromptUKFT


def _build_prompt(
    descriptions: List[str],
    system: str,
    instructions: List[str],
    lang: Optional[str] = None,
    prompt_path: str = "& prompts/system",
    default_entry: str = "prompt.jinja",
) -> PromptUKFT:
    """\
    Build a PromptUKFT from processed descriptions, system prompt, and instructions.

    This is a common utility function used by build_autotask_prompt, build_autofunc_prompt,
    and build_autocode_prompt to create PromptUKFT instances.

    Args:
        descriptions: List of description strings (already processed, no None values).
        system: System prompt string (already processed with default if needed).
        instructions: List of instruction strings (already processed, no None values).
        lang: Language code for localization.
        prompt_path: Path to the prompt template folder.
        default_entry: Default template entry name.

    Returns:
        PromptUKFT: A PromptUKFT instance configured with the provided parameters.
    """
    return PromptUKFT.from_path(
        prompt_path,
        default_entry=default_entry,
        binds={
            "system": system,
            "descriptions": descriptions,
            "instructions": instructions,
        },
        lang=lang,
    )
