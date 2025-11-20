"""\
autotask utilities for AgentHeaven.

This module provides the `autotask` function that creates callable functions
automatically implemented using Large Language Models (LLMs) based on
examples and task descriptions.

The function infers the task logic from provided examples and applies it
to new inputs, without requiring explicit function implementation.
"""

__all__ = [
    "autotask",
]

from typing import List, Dict, Any, Callable, Optional, Iterable, Union

from ..basic.log_utils import get_logger

logger = get_logger(__name__)

from ..basic.debug_utils import AutoFuncError
from ..basic.parser_utils import parse_md
from ...llm import LLM
from ...cache import CacheEntry
from ...ukf.templates.basic.prompt import PromptUKFT


def autotask(
    prompt: Optional[PromptUKFT] = None,
    descriptions: Optional[Union[str, List[str]]] = None,
    system: Optional[str] = None,
    examples: Optional[Iterable[Union[Dict[str, Any], CacheEntry]]] = None,
    instructions: Optional[List[str]] = None,
    lang: Optional[str] = None,
    llm_args: Optional[Dict] = None,
) -> Callable:
    """\
    Create a function that is automatically implemented using LLM inference.

    This function infers task logic from the provided description and examples,
    then applies it to new inputs using an LLM. Uses PromptUKFT for template
    rendering with structured prompt generation.

    Args:
        prompt (Optional[PromptUKFT]): A pre-defined PromptUKFT template to use for the task.
            If None, a default prompt will be constructed using the provided descriptions and examples.
            If not None, the prompt will be used directly and other parameters (descriptions, system, examples, instructions) will be ignored.
            (TODO: behavior of other parameters -> update prompt)
        descriptions (Union[str, List[str]]): Task description(s) that explain what the function should do.
        system (Optional[str]): A single system prompt to guide the LLM's behavior.
        examples (Iterable[Union[Dict[str, Any], CacheEntry]], optional): A list of examples demonstrating
            the desired input-output behavior. Each example should be a dictionary with 'inputs' and 'output'/'expected' keys,
            or a CacheEntry object. Expected is preferred over output if both are provided. Defaults to None.
        instructions (Union[str, List[str]], optional): Additional instructions to guide the LLM's response.
        lang (str, optional): Language code for localization (e.g., "en" for English).
        llm_args (Dict, optional): Arguments for the LLM model (e.g., {"model": "gemini-flash"}).
            If None, uses default LLM configuration.

    Returns:
        Any: The LLM-inferred output for the given inputs, parsed from the response.

    Raises:
        AutoFuncError: If the LLM fails to generate valid output or
            if there's an error during execution.

    Examples:
        >>> f = autotask(
        ...     descriptions="Square the input number",
        ...     examples=[
        ...         {"inputs": {"x": 5}, "output": 25},
        ...         {"inputs": {"x": 3}, "output": 9},
        ...     ],
        ...     llm_args={"preset": "tiny"}
        ... )
        >>> f(x=4)
        16

        >>> f = autotask(
        ...     descriptions="Sentiment analysis. Rate the sentiment of the text from 1 to 10. Return an integer.",
        ...     examples=[
        ...         {"inputs": {"text": "An absolute masterpiece!"}, "expected": 10},
        ...         {"inputs": {"text": "What a letdown."}, "expected": 3},
        ...         {"inputs": {"text": "It was fine."}, "expected": 6},
        ...     ],
        ...     llm_args={"preset": "tiny"}
        ... )
        >>> f(text="The plot was engaging but the ending was predictable.")
        7   # or maybe 6/8/9, depending on LLM interpretation
    """
    if prompt is None:
        if descriptions is None:
            raise ValueError("Either `prompt` or `descriptions` must be provided to define the task.")
        system_prompt = (
            system
            or "You are a helpful AI assistant. Your task is to complete a task given its description, examples, and new inputs. Infer the task's logic from the examples and apply it to the new inputs."
        )
        desc_list = [descriptions] if isinstance(descriptions, str) else descriptions
        examples_list = [example if isinstance(example, CacheEntry) else CacheEntry.from_dict(data=example) for example in examples] if examples else list()
        instr_list = (([instructions] if isinstance(instructions, str) else instructions) or list()) + [
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

    def autotask_function(
        hints: Optional[Union[str, List[str]]] = None,
        **inputs: Dict[str, Any],
    ) -> Any:
        hints = ([hints] if isinstance(hints, str) else hints) or list()
        instance = CacheEntry.from_args(**inputs, output=..., metadata={"hints": hints})
        try:
            prompt_str = prompt.text(lang=lang, instance=instance).rstrip()
        except Exception as e:
            raise AutoFuncError(f"Failed to render prompt for autotask function.\nInstance:\n{instance}\nError: {e}") from e
        logger.debug(f"Autotask function prompt:\n{prompt_str}")
        try:
            response = llm.oracle(prompt_str)
        except Exception as e:
            raise AutoFuncError(f"LLM failed to generate response for autotask function.\nPrompt:\n{prompt_str}\nError: {e}") from e
        logger.debug(f"Autotask function LLM response:\n{response}")
        try:
            parsed = parse_md(response)
            output_repr = parsed.get("output", "").strip()
            try:
                return eval(output_repr)
            except Exception as e:
                logger.debug(
                    f"Failed to eval autotask output representation from LLM response. Falling back to raw output.\nPrompt:\n{prompt_str}\nError: {e}\nOutput repr:\n{output_repr}"
                )
                return output_repr
        except Exception as e:
            raise AutoFuncError(f"Failed to parse LLM response for autotask function.\nPrompt:\n{prompt_str}\nResponse:\n{response}\nError: {e}") from e

    return autotask_function
