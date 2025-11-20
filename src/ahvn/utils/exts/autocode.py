"""\
autocode utilities for AgentHeaven.

This module provides the `autocode` function that creates static callable functions
automatically implemented using Large Language Models (LLMs) based on
function specifications and examples.

The function generates a complete Python implementation from examples and executes
the code to create a static callable function (not LLM-based).
"""

__all__ = [
    "autocode",
]

from typing import List, Dict, Any, Callable, Optional, Iterable, Union

from ..basic.log_utils import get_logger

logger = get_logger(__name__)

from ..basic.debug_utils import AutoFuncError
from ..basic.parser_utils import parse_md
from ..basic.func_utils import code2func
from ...llm import LLM
from ...cache import CacheEntry
from ...tool import ToolSpec
from ...ukf.templates.basic.prompt import PromptUKFT
from ...ukf.templates.basic import ExperienceUKFT


def autocode(
    func_spec: Optional[Union[Callable, ToolSpec]] = None,
    descriptions: Optional[Union[str, List[str]]] = None,
    system: Optional[str] = None,
    examples: Optional[Iterable[Union[Dict[str, Any], CacheEntry]]] = None,
    instructions: Optional[Union[str, List[str]]] = None,
    env: Optional[Dict] = None,
    lang: Optional[str] = None,
    llm_args: Optional[Dict] = None,
) -> Callable:
    """\
    Create a static function that is automatically generated using LLM code generation.

    This function takes a function specification and examples, then uses an LLM to
    generate a complete implementation. The generated code is executed to return a
    static callable function (not LLM-based).

    Can be used as a decorator or as a regular function call.

    Args:
        func_spec (Union[Callable, ToolSpec], optional): The function specification.
        descriptions (Union[str, List[str]], optional): Additional descriptions for the task.
        system (str, optional): System prompt to guide the LLM's behavior.
        examples (Iterable[Union[Dict[str, Any], CacheEntry]], optional): Examples demonstrating
            the desired input-output behavior.
        instructions (Union[str, List[str]], optional): Additional instructions for the LLM.
        env (Optional[Dict], optional): The environment in which to execute the code. Defaults to None.
        lang (str, optional): Language code for localization.
        llm_args (Dict, optional): Arguments for the LLM model.
            Notice that code generation oughts to be called once and then reused.
            Therefore, it is recommended to use a high-quality LLM with `cache` enabled.

    Returns:
        Callable: A static callable function generated from the LLM-generated code.

    Raises:
        AutoFuncError: If the LLM fails to generate valid code or execution fails.

    Examples:
        >>> @autocode(examples=[{"inputs": {"x": 5}, "output": 25}])
        >>> def square(x: int) -> int:
        ...     pass
        >>> square(x=4)
        16
    """

    def _create_autocode(func_spec: Union[Callable, ToolSpec]) -> Callable:
        if not isinstance(func_spec, ToolSpec):
            func_spec = ToolSpec.from_function(func_spec)
        func_name = func_spec.binded.name

        system_prompt = (
            system
            or "You are a skillful Python expert. Your task is to generate a complete Python function implementation based on the provided signature and test cases."
        )
        examples_list = [example if isinstance(example, CacheEntry) else CacheEntry.from_dict(data=example) for example in examples] if examples else list()
        assertions = [ExperienceUKFT.from_cache_entry(example).text(composer="assertion") for example in examples_list if example]
        func_demonstration_str = func_spec.code
        if assertions:
            assertsions_str = "\n".join(assertions)
            func_demonstration_str += f"\n\n# Test cases that your implementation must pass:\n{assertsions_str}"
        func_signature_str = "Implement the following function:\n"
        func_signature_str += f"```python\n{func_demonstration_str.strip()}\n```"
        desc_list = [func_signature_str] + (([descriptions] if isinstance(descriptions, str) else descriptions) if descriptions else [])
        instr_list = (([instructions] if isinstance(instructions, str) else instructions) if instructions else []) + [
            "Analyze the function signature and test cases to understand the required logic.",
            "Generate a complete Python function implementation that passes all the test cases.",
            "Preserve the exact function signature including name, parameters, type hints, and return type.",
            "Include necessary imports at the top level if needed.",
            "DO NOT include the test assertions in your output - only generate the function implementation.",
            "Wrap the complete Python code in a single markdown 'python' code block.",
        ]

        prompt = PromptUKFT.from_path(
            "& prompts/autocode",
            default_entry="prompt.jinja",
            binds={
                "system": system_prompt,
                "descriptions": list(filter(lambda x: x is not None, desc_list)),
                "examples": examples_list,
                "instructions": list(filter(lambda x: x is not None, instr_list)),
            },
        )

        llm = LLM(**(llm_args or dict()))

        try:
            prompt_str = prompt.text(lang=lang).rstrip()
        except Exception as e:
            raise AutoFuncError(f"Failed to render prompt for autocode function.\nError: {e}") from e
        logger.debug(f"Autocode function prompt:\n{prompt_str}")

        try:
            response = llm.oracle(prompt_str)
        except Exception as e:
            raise AutoFuncError(f"LLM failed to generate response for autocode function.\nPrompt:\n{prompt_str}\nError: {e}") from e
        logger.debug(f"Autocode function LLM response:\n{response}")

        try:
            parsed = parse_md(response)
            code_block = parsed.get("python", "").strip()
            if not code_block:
                raise ValueError("No python code block found in LLM response")
        except Exception as e:
            raise AutoFuncError(f"Unable to correctly parse `python` code block from the LLM response.\nPrompt:\n{prompt_str}\nResponse:\n{response}") from e
        logger.debug(f"Extracted code block:\n{code_block}")

        try:
            func = code2func(code=code_block, func_name=func_name, env=env)
            if func is None or not callable(func):
                raise ValueError(f"No callable function '{func_name}' found in generated code")

            return func
        except Exception as e:
            raise AutoFuncError(f"Failed to execute generated code.\nCode:\n{code_block}\nError: {e}") from e

    if (
        func_spec is not None
        and callable(func_spec)
        and descriptions is None
        and system is None
        and examples is None
        and instructions is None
        and lang is None
        and llm_args is None
    ):
        return _create_autocode(func_spec)

    if func_spec is not None:
        return _create_autocode(func_spec)

    def decorator(func: Callable) -> Callable:
        return _create_autocode(func)

    return decorator
