"""\
autofunc utilities for AgentHeaven.

This module provides the `autofunc` function that creates callable functions
automatically implemented using Large Language Models (LLMs) based on
function specifications and inputs.

The function asks the LLM to be a skillful python expert and produce output
given function specification and inputs. It should support `Callable` and `ToolSpec`.
"""

__all__ = [
    "autofunc",
]

from typing import List, Dict, Any, Callable, Optional, Iterable, Union

from ..basic.log_utils import get_logger

logger = get_logger(__name__)

from ..basic.debug_utils import AutoFuncError
from ..basic.parser_utils import parse_md
from ...llm import LLM
from ...cache import CacheEntry
from ...tool import ToolSpec
from ...ukf.templates.basic.prompt import PromptUKFT


def autofunc(
    func_spec: Optional[Union[Callable, ToolSpec]] = None,
    descriptions: Optional[Union[str, List[str]]] = None,
    system: Optional[str] = None,
    examples: Optional[Iterable[Union[Dict[str, Any], CacheEntry]]] = None,
    instructions: Optional[Union[str, List[str]]] = None,
    lang: Optional[str] = None,
    llm_args: Optional[Dict] = None,
) -> Callable:
    """\
    Create a function that is automatically implemented using LLM inference.

    This function asks the LLM to be a skillful Python expert and produce output
    given function specification and inputs. Uses PromptUKFT for template
    rendering with structured prompt generation.

    Can be used as a decorator or as a regular function call.

    Args:
        func_spec (Union[Callable, ToolSpec], optional): The function specification.
        descriptions (Union[str, List[str]], optional): Additional descriptions for the task.
        system (str, optional): System prompt to guide the LLM's behavior.
        examples (Iterable[Union[Dict[str, Any], CacheEntry]], optional): Examples demonstrating
            the desired input-output behavior.
        instructions (Union[str, List[str]], optional): Additional instructions for the LLM.
        lang (str, optional): Language code for localization.
        llm_args (Dict, optional): Arguments for the LLM model.

    Returns:
        Callable: A function that takes keyword arguments matching the function specification
            and returns the LLM-inferred output.

    Raises:
        AutoFuncError: If the LLM fails to generate valid output or execution fails.

    Examples:
        >>> # Usage 1: Direct function call
        >>> def square(x: int) -> int:
        ...     '''Return the square of x.'''
        ...     pass
        >>> f = autofunc(square, llm_args={"preset": "tiny"})
        >>> f(x=5)
        25

        >>> # Usage 2: As a decorator with arguments
        >>> @autofunc(examples=[{"inputs": {"x": 5}, "output": 25}], llm_args={"preset": "tiny"})
        >>> def square(x: int) -> int:
        ...     '''Return the square of x.'''
        ...     pass
        >>> square(x=4)
        16

        >>> # Usage 3: As a decorator without arguments
        >>> @autofunc
        >>> def add(x: int, y: int) -> int:
        ...     '''Add two numbers.'''
        ...     pass
        >>> add(x=3, y=4)
        7
    """

    def _create_autofunc(func_spec: Union[Callable, ToolSpec]) -> Callable:
        if not isinstance(func_spec, ToolSpec):
            func_spec_obj = ToolSpec.from_function(func_spec)
        else:
            func_spec_obj = func_spec

        system_prompt = system or "You are a skillful Python expert. Your task is to act as a function and produce output given its specification and inputs."
        desc_list = (([descriptions] if isinstance(descriptions, str) else descriptions) if descriptions else []) + [
            "## Function Specification",
            f"```python\n{func_spec_obj.code}\n```",
        ]
        examples_list = [example if isinstance(example, CacheEntry) else CacheEntry.from_dict(data=example) for example in examples] if examples else list()
        instr_list = (([instructions] if isinstance(instructions, str) else instructions) if instructions else []) + [
            "Keep your reasoning or response as brief as possible.",
            "The final answer must be a string that supports python `repr`.",
            "Wrap the final answer in `<output></output>` tags.",
        ]

        prompt = PromptUKFT.from_path(
            "& prompts/system",
            default_entry="prompt.jinja",
            binds={
                "system": system_prompt,
                "descriptions": list(filter(lambda x: x is not None, desc_list)),
                "examples": examples_list,
                "instructions": list(filter(lambda x: x is not None, instr_list)),
            },
        )

        llm = LLM(**(llm_args or dict()))

        def autofunc_function(
            hints: Optional[Union[str, List[str]]] = None,
            **inputs: Dict[str, Any],
        ) -> Any:
            hints = ([hints] if isinstance(hints, str) else hints) or list()
            instance = CacheEntry.from_args(**inputs, output=..., metadata={"hints": hints})
            try:
                prompt_str = prompt.text(lang=lang, instance=instance).rstrip()
            except Exception as e:
                raise AutoFuncError(f"Failed to render prompt for autofunc function.\nInstance:\n{instance}\nError: {e}") from e
            logger.debug(f"Autofunc function prompt:\n{prompt_str}")
            try:
                response = llm.oracle(prompt_str)
            except Exception as e:
                raise AutoFuncError(f"LLM failed to generate response for autofunc function.\nPrompt:\n{prompt_str}\nError: {e}") from e
            logger.debug(f"Autofunc function LLM response:\n{response}")
            try:
                parsed = parse_md(response)
                output_repr = parsed.get("output", "").strip()
                try:
                    return eval(output_repr)
                except Exception as e:
                    logger.debug(
                        f"Failed to eval autofunc output representation from LLM response. Falling back to raw output.\nPrompt:\n{prompt_str}\nError: {e}\nOutput repr:\n{output_repr}"
                    )
                    return output_repr
            except Exception as e:
                raise AutoFuncError(f"Failed to parse LLM response for autofunc function.\nPrompt:\n{prompt_str}\nResponse:\n{response}\nError: {e}") from e

        return autofunc_function

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
        return _create_autofunc(func_spec)

    if func_spec is not None:
        return _create_autofunc(func_spec)

    def decorator(func: Callable) -> Callable:
        return _create_autofunc(func)

    return decorator
