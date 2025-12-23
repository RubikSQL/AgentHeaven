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
    "autofunc_prompt_composer",
    "build_autofunc_base_prompt",
]

from typing import List, Dict, Any, Callable, Optional, Iterable, Union

from ..basic.log_utils import get_logger

logger = get_logger(__name__)

from ..basic.debug_utils import AutoFuncError
from ..basic.parser_utils import parse_md
from ..basic.jinja_utils import get_lang_instruction
from ...llm import LLM
from ...cache import CacheEntry
from ...tool import ToolSpec
from ...ukf.templates.basic.prompt import PromptUKFT
from ...ukf.templates.basic.experience import ExperienceUKFT
from ...klstore.base import BaseKLStore
from ...klengine.base import BaseKLEngine
from ...klbase.base import KLBase
from .examples_utils import normalize_examples


def autofunc_prompt_composer(
    kl: PromptUKFT,
    func_spec: Union[Callable, ToolSpec],
    system: Optional[str] = None,
    descriptions: Optional[Union[str, List[str]]] = None,
    examples: Optional[
        Union[
            Iterable[Union[Dict[str, Any], CacheEntry, ExperienceUKFT]],
            BaseKLStore,
            BaseKLEngine,
            KLBase,
        ]
    ] = None,
    instructions: Optional[Union[str, List[str]]] = None,
    instance: Optional[CacheEntry] = None,
    search_args: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> str:
    if not isinstance(func_spec, ToolSpec):
        func_spec = ToolSpec.from_function(func_spec)

    system = system or kl.get("binds", dict()).get("system", "")
    system = system or kl.get("binds", dict()).get("default_system", "")
    descriptions = descriptions or kl.get("binds", dict()).get("descriptions", list())
    desc_list = (
        ["## Function Specification", f"```python\n{func_spec.code}\n```"]
        + kl.get("binds", dict()).get("default_descriptions", list())
        + (([descriptions] if isinstance(descriptions, str) else descriptions) if descriptions else [])
    )
    instructions = instructions or kl.get("binds", dict()).get("instructions", list())
    inst_list = (
        kl.get("binds", dict()).get("default_instructions", list())
        + (([instructions] if isinstance(instructions, str) else instructions) if instructions else [])
        + ([get_lang_instruction(kwargs.get("lang"))] if kwargs.get("lang") else [])
    )
    examples = examples or kl.get("binds", dict()).get("examples", None)
    default_examples = kl.get("binds", dict()).get("default_examples", list())
    search_args = search_args or kl.get("binds", dict()).get("search_args", None)
    examples_list = list(normalize_examples(examples, search_args=search_args)) + list(normalize_examples(default_examples))

    return kl.format(
        composer="prompt",
        system=system,
        descriptions=list(filter(lambda x: x is not None, desc_list)),
        instructions=list(filter(lambda x: x is not None, inst_list)),
        instance=instance,
        examples=list(filter(lambda x: x is not None, examples_list)),
        **kwargs,
    )


def build_autofunc_base_prompt() -> PromptUKFT:
    prompt_kl = PromptUKFT.from_path(
        "& prompts/system",
        name="autofunc",
        default_entry="prompt.jinja",
        binds={
            "default_system": "You are a skillful Python expert. Your task is to act as a function and produce output given its specification and inputs.",
            "default_descriptions": list(),
            "default_examples": list(),
            "default_instructions": [
                "Keep your reasoning or response as brief as possible.",
                "The final answer must be a string that supports python `repr`.",
                "Wrap the final answer in `<output></output>` tags.",
            ],
        },
    )
    prompt_kl.set_composer("autofunc", autofunc_prompt_composer)
    prompt_kl.set_composer("default", autofunc_prompt_composer)
    return prompt_kl


def autofunc(
    func_spec: Optional[Union[Callable, ToolSpec]] = None,
    prompt: Optional[PromptUKFT] = None,
    system: Optional[str] = None,
    descriptions: Optional[Union[str, List[str]]] = None,
    examples: Optional[
        Union[
            Iterable[Union[Dict[str, Any], CacheEntry, ExperienceUKFT]],
            BaseKLStore,
            BaseKLEngine,
            KLBase,
        ]
    ] = None,
    instructions: Optional[Union[str, List[str]]] = None,
    composer: str = "autofunc",
    lang: Optional[str] = None,
    llm_args: Optional[Dict] = None,
    search_args: Optional[Dict] = None,
    capture: Optional[Dict] = None,
    **kwargs,
) -> Callable:
    """\
    Create a function that is automatically implemented using LLM inference.

    This function asks the LLM to be a skillful Python expert and produce output
    given function specification and inputs. Uses PromptUKFT for template
    rendering with structured prompt generation.

    Can be used as a decorator or as a regular function call.

    Args:
        func_spec (Union[Callable, ToolSpec], optional): The function specification.
        prompt (Optional[PromptUKFT]): A pre-defined PromptUKFT template to use for the function.
            If None, a default prompt will be constructed using the provided func_spec and other parameters.
            If not None, the prompt will be used directly and other parameters (func_spec, descriptions, system, examples, instructions) will be ignored.
            (TODO: behavior of other parameters -> update prompt)
        system (str, optional): System prompt to guide the LLM's behavior.
        descriptions (Union[str, List[str]], optional): Additional descriptions for the task.
        examples (Iterable[Union[Dict[str, Any], CacheEntry]], optional): Examples demonstrating
            the desired input-output behavior.
        instructions (Union[str, List[str]], optional): Additional instructions for the LLM.
        composer (str, optional): The prompt composer to use. Defaults to "autofunc".
        lang (str, optional): Language code for localization.
        llm_args (Dict, optional): Arguments for the LLM model.
        search_args (Dict, optional): Arguments for searching examples from example sources.
            It is used only when `examples` is a KL example source (KLStore, KLEngine, KLBase).
        capture (Dict, optional): Capture settings for logging or debugging.
            If provided, it will be used to capture the execution details.
            - 'prompt': The constructed prompt object.
        kwargs: Additional keyword arguments.

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
    if prompt is None:
        prompt = build_autofunc_base_prompt()
    else:
        prompt = prompt.clone()
    prompt = prompt.bind(
        **(
            ({"system": system} if system is not None else {})
            | ({"descriptions": descriptions} if descriptions is not None else {})
            | ({"examples": examples} if examples is not None else {})
            | ({"instructions": instructions} if instructions is not None else {})
            | ({"search_args": search_args} if search_args is not None else {})
            | kwargs
            if kwargs is not None
            else {}
        ),
    )
    if capture is not None:
        capture["prompt"] = prompt

    llm = LLM(**(llm_args or dict()))

    def _create_autofunc(func_spec: Union[Callable, ToolSpec]) -> Callable:
        if not isinstance(func_spec, ToolSpec):
            func_spec = ToolSpec.from_function(func_spec, parse_docstring=True)

        def autofunc_function(
            hints: Optional[Union[str, List[str]]] = None,
            **inputs: Dict[str, Any],
        ) -> Any:
            hints = ([hints] if isinstance(hints, str) else hints) or list()
            instance = CacheEntry.from_args(**inputs, output=..., metadata={"hints": hints})
            try:
                prompt_str = prompt.format(
                    composer=composer,
                    func_spec=func_spec,
                    instance=instance,
                    lang=lang,
                ).rstrip()
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

    if func_spec is not None:
        return _create_autofunc(func_spec=func_spec)

    def decorator(func_spec: Union[Callable, ToolSpec]) -> Callable:
        return _create_autofunc(func_spec=func_spec)

    return decorator
