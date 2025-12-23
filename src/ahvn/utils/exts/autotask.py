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
    "autotask_prompt_composer",
    "build_autotask_base_prompt",
]

from typing import List, Dict, Any, Callable, Optional, Iterable, Union

from ..basic.log_utils import get_logger
from ..basic.serialize_utils import loads_json, dumps_json

logger = get_logger(__name__)

from ..basic.debug_utils import AutoFuncError
from ..basic.parser_utils import parse_md
from ..basic.jinja_utils import get_lang_instruction
from ...llm import LLM
from ...cache import CacheEntry
from ...ukf.templates.basic.prompt import PromptUKFT
from ...ukf.templates.basic.experience import ExperienceUKFT
from ...klstore.base import BaseKLStore
from ...klengine.base import BaseKLEngine
from ...klbase.base import KLBase
from .examples_utils import normalize_examples


def autotask_prompt_composer(
    kl: PromptUKFT,
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
    system = system or kl.get("binds", dict()).get("system", "")
    system = system or kl.get("binds", dict()).get("default_system", "")
    descriptions = descriptions or kl.get("binds", dict()).get("descriptions", list())
    desc_list = kl.get("binds", dict()).get("default_descriptions", list()) + (
        ([descriptions] if isinstance(descriptions, str) else descriptions) if descriptions else []
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


def build_autotask_base_prompt(output_schema: Dict[str, Any]) -> PromptUKFT:
    mode = None if output_schema is None else output_schema.get("mode", "base")
    prompt_kl = PromptUKFT.from_path(
        "& prompts/system",
        name="autotask" if mode is None else ("autotask" + f"_{mode}"),
        default_entry="prompt.jinja",
        binds={
            "default_system": "You are a helpful AI assistant. Your task is to complete a task given its description, examples, and new inputs. Infer the task's logic from the examples and apply it to the new inputs.",
            "default_descriptions": list(),
            "default_examples": list(),
            "default_instructions": [
                "Keep your reasoning or response as brief as possible.",
            ]
            + ([] if mode is None else [])
            + ([] if mode == "base" else [])
            + (
                [
                    "The final answer must be a string that supports python `repr`.",
                ]
                if mode == "repr"
                else []
            )
            + (
                [
                    "The final answer must be a markdown code block containing a valid JSON object using '```json'.",
                ]
                if mode == "json"
                else []
            )
            + (
                [
                    "The final answer must be a markdown code block using '```'.",
                ]
                if mode == "code"
                else []
            )
            + [
                "Wrap the final answer in `<output></output>` tags.",
            ],
        },
    )
    prompt_kl.set_composer("autotask", autotask_prompt_composer)
    prompt_kl.set_composer("default", autotask_prompt_composer)
    prompt_kl.bind(output_schema=output_schema)
    return prompt_kl


def autotask(
    prompt: Optional[PromptUKFT] = None,
    descriptions: Optional[Union[str, List[str]]] = None,
    system: Optional[str] = None,
    examples: Optional[
        Union[
            Iterable[Union[Dict[str, Any], CacheEntry, ExperienceUKFT]],
            BaseKLStore,
            BaseKLEngine,
            KLBase,
        ]
    ] = None,
    instructions: Optional[Union[str, List[str]]] = None,
    output_schema: Optional[Dict[str, Any]] = None,
    composer: str = "autotask",
    lang: Optional[str] = None,
    llm_args: Optional[Dict] = None,
    search_args: Optional[Dict] = None,
    capture: Optional[Dict] = None,
    **kwargs,
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
        output_schema (Dict[str, Any], optional): Schema defining the expected output format.
            This will affect how the prompt instructions are generated regarding the output format.
            If None, defaults to {"mode": "base"}.
        composer (str, optional): The prompt composer to use. Defaults to "autotask".
        lang (str, optional): Language code for localization (e.g., "en" for English).
        llm_args (Dict, optional): Arguments for the LLM model (e.g., {"model": "gemini-flash"}).
            If None, uses default LLM configuration.
        search_args (Dict, optional): Arguments for searching examples from example sources.
            It is used only when `examples` is a KL example source (KLStore, KLEngine, KLBase).
        capture (Dict, optional): Capture settings for logging or debugging.
            If provided, it will be used to capture the execution details.
            - 'prompt': The constructed prompt object.
        kwargs: Additional keyword arguments.

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
        ...     output_schema={"mode": "repr"},
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
        ...     output_schema={"mode": "repr"},
        ...     llm_args={"preset": "tiny"}
        ... )
        >>> f(text="The plot was engaging but the ending was predictable.")
        7   # or maybe 6/8/9, depending on LLM interpretation
    """
    if prompt is None:
        prompt = build_autotask_base_prompt(output_schema=output_schema or {"mode": "base"})
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
    output_schema = output_schema or prompt.get("binds", dict()).get("output_schema", dict()) or {"mode": "base"}
    mode = output_schema.get("mode", "base")
    code_lang = output_schema.get("args", dict()).get("language", "python")
    logger.debug(f"Autotask function output schema: {dumps_json(output_schema)}")

    llm = LLM(**(llm_args or dict()))

    def autotask_function(
        hints: Optional[Union[str, List[str]]] = None,
        **inputs: Dict[str, Any],
    ) -> Any:
        hints = ([hints] if isinstance(hints, str) else hints) or list()
        instance = CacheEntry.from_args(**inputs, output=..., metadata={"hints": hints})
        try:
            prompt_str = prompt.format(
                composer=composer,
                instance=instance,
                lang=lang,
            ).rstrip()
        except Exception as e:
            raise AutoFuncError(f"Failed to render prompt for autotask function.\nInstance:\n{instance}\nError: {e}") from e
        logger.debug(f"Autotask function prompt:\n{prompt_str}")
        try:
            response = llm.oracle(prompt_str)
        except Exception as e:
            raise AutoFuncError(f"LLM failed to generate response for autotask function.\nPrompt:\n{prompt_str}\nError: {e}") from e
        logger.debug(f"Autotask function LLM response:\n{response}")
        try:
            parsed = parse_md(response, recurse=True)
        except Exception as e:
            raise AutoFuncError(f"Failed to parse LLM response for autotask function.\nPrompt:\n{prompt_str}\nResponse:\n{response}\nError: {e}") from e
        if mode == "base":
            return str(parsed.get("output.text", "")).strip()
        elif mode == "json":
            try:
                return loads_json(str(parsed.get("output.json", "{}")).strip())
            except Exception as e:
                raise AutoFuncError(
                    f"Failed to parse autotask output JSON from LLM response.\nPrompt:\n{prompt_str}\nError: {e}\nResponse:\n{response}\nParsed:\n{dumps_json(parsed)}"
                ) from e
        elif mode == "code":
            try:
                return str(parsed.get(f"output.{code_lang}", "")).strip()
            except Exception as e:
                raise AutoFuncError(
                    f"Failed to extract autotask output code from LLM response.\nPrompt:\n{prompt_str}\nError: {e}\nResponse:\n{response}\nParsed:\n{dumps_json(parsed)}"
                ) from e
        elif mode == "repr":
            try:
                return eval(parsed.get("output.text", "").strip())
            except Exception as e:
                logger.debug(
                    f"Failed to eval autotask output representation from LLM response. Falling back to raw output.\nPrompt:\n{prompt_str}\nError: {e}\nResponse:\n{response}\nParsed:\n{dumps_json(parsed)}"
                )
        else:
            return str(parsed.get("output.text", "")).strip()

    return autotask_function
