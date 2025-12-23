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
    "autocode_prompt_composer",
    "build_autocode_base_prompt",
]

from typing import List, Dict, Any, Callable, Optional, Iterable, Union

from ..basic.log_utils import get_logger

logger = get_logger(__name__)

from ..basic.debug_utils import AutoFuncError
from ..basic.parser_utils import parse_md
from ..basic.func_utils import code2func, funcwrap
from ..basic.jinja_utils import get_lang_instruction
from ...llm import LLM
from ...cache import CacheEntry
from ...tool import ToolSpec
from ...ukf.templates.basic.prompt import PromptUKFT
from ...ukf.templates.basic.experience import ExperienceUKFT
from ...klstore.base import BaseKLStore
from ...klengine.base import BaseKLEngine
from ...klbase.base import KLBase
from .examples_utils import normalize_examples, ExampleSource


def autocode_prompt_composer(
    kl: PromptUKFT,
    func_spec: Union[Callable, ToolSpec],
    system: Optional[str] = None,
    descriptions: Optional[Union[str, List[str]]] = None,
    examples: Optional[ExampleSource] = None,
    instructions: Optional[Union[str, List[str]]] = None,
    search_args: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> str:
    if not isinstance(func_spec, ToolSpec):
        func_spec = ToolSpec.from_function(func_spec)

    examples = examples or kl.get("binds", dict()).get("examples", None)
    default_examples = kl.get("binds", dict()).get("default_examples", list())
    search_args = search_args or kl.get("binds", dict()).get("search_args", None)
    examples_list = list(normalize_examples(examples, search_args=search_args)) + list(normalize_examples(default_examples))

    if examples_list:
        assertions = [ExperienceUKFT.from_cache_entry(example).text(composer="assertion") for example in examples_list if example]
        func_demonstration_str = func_spec.code
        assertsions_str = "\n".join(assertions)
        func_demonstration_str += f"\n\n# Test cases that your implementation must pass:\n{assertsions_str}"
        func_signature_str = "Implement the following function:\n"
        func_signature_str += f"```python\n{func_demonstration_str.strip()}\n```"
    else:
        func_signature_str = "Implement the following function:\n"
        func_signature_str += f"```python\n{func_spec.code.strip()}\n```"

    system = system or kl.get("binds", dict()).get("system", "")
    system = system or kl.get("binds", dict()).get("default_system", "")
    descriptions = descriptions or kl.get("binds", dict()).get("descriptions", list())
    desc_list = (
        [func_signature_str]
        + kl.get("binds", dict()).get("default_descriptions", list())
        + (([descriptions] if isinstance(descriptions, str) else descriptions) if descriptions else [])
    )
    instructions = instructions or kl.get("binds", dict()).get("instructions", list())
    inst_list = (
        kl.get("binds", dict()).get("default_instructions", list())
        + (([instructions] if isinstance(instructions, str) else instructions) if instructions else [])
        + ([get_lang_instruction(kwargs.get("lang"))] if kwargs.get("lang") else [])
    )

    return kl.format(
        composer="prompt",
        system=system,
        descriptions=list(filter(lambda x: x is not None, desc_list)),
        instructions=list(filter(lambda x: x is not None, inst_list)),
        examples=list(filter(lambda x: x is not None, examples_list)),
        **kwargs,
    )


def build_autocode_base_prompt() -> PromptUKFT:
    prompt_kl = PromptUKFT.from_path(
        "& prompts/system",
        name="autocode",
        default_entry="prompt.jinja",
        binds={
            "default_system": "You are a skillful Python expert. Your task is to generate a complete Python function implementation based on the provided signature and test cases.",
            "default_descriptions": list(),
            "default_examples": list(),
            "default_instructions": [
                "Analyze the function signature and test cases to understand the required logic.",
                "Generate a complete Python function implementation that passes all the test cases.",
                "Preserve the exact function signature including name, parameters, type hints, and return type.",
                "Include necessary imports at the top level if needed.",
                "DO NOT include the test assertions in your output - only generate the function implementation.",
                "Wrap the complete Python code in a single markdown 'python' code block.",
            ],
        },
    )
    prompt_kl.set_composer("autocode", autocode_prompt_composer)
    prompt_kl.set_composer("default", autocode_prompt_composer)
    return prompt_kl


# TODO: Actually run the assertions to verify correctness
# TODO: Make sure the generated code is reused (update strategy?
def autocode(
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
    env: Optional[Dict] = None,
    composer: str = "autocode",
    lang: Optional[str] = None,
    llm_args: Optional[Dict] = None,
    search_args: Optional[Dict] = None,
    capture: Optional[Dict] = None,
    **kwargs,
) -> Callable:
    """\
    Create a static function that is automatically generated using LLM code generation.

    This function takes a function specification and examples, then uses an LLM to
    generate a complete implementation. The generated code is executed to return a
    static callable function (not LLM-based).

    Can be used as a decorator or as a regular function call.

    Args:
        func_spec (Union[Callable, ToolSpec], optional): The function specification.
        prompt (Optional[PromptUKFT]): A pre-defined PromptUKFT template to use for code generation.
            If None, a default prompt will be constructed using the provided func_spec and other parameters.
            If not None, the prompt will be used directly and other parameters (func_spec, descriptions, system, examples, instructions) will be ignored.
            (TODO: behavior of other parameters -> update prompt)
        system (str, optional): System prompt to guide the LLM's behavior.
        descriptions (Union[str, List[str]], optional): Additional descriptions for the task.
        examples (Iterable[Union[Dict[str, Any], CacheEntry]], optional): Examples demonstrating
            the desired input-output behavior.
        instructions (Union[str, List[str]], optional): Additional instructions for the LLM.
        env (Optional[Dict], optional): The environment in which to execute the code. Defaults to None.
        composer (str, optional): The prompt composer to use. Defaults to "autocode".
        lang (str, optional): Language code for localization.
        llm_args (Dict, optional): Arguments for the LLM model.
            Notice that code generation oughts to be called once and then reused.
            Therefore, it is strongly recommended to use a high-quality LLM, and
            it is also strongly recommended to have `cache` enabled to avoid repeated code generation calls.
        search_args (Dict, optional): Arguments for searching examples from example sources.
            It is used only when `examples` is a KL example source (KLStore, KLEngine, KLBase).
        capture (Dict, optional): Capture settings for logging or debugging.
            If provided, it will be used to capture the execution details.
            - 'prompt': The constructed prompt object.
        kwargs: Additional keyword arguments.

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
    if prompt is None:
        prompt = build_autocode_base_prompt()
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

    def _build_autocode(func_spec: Union[Callable, ToolSpec]) -> Callable:
        if not isinstance(func_spec, ToolSpec):
            func_spec = ToolSpec.from_function(func_spec, parse_docstring=True)
        func_name = func_spec.binded.name

        def autocode_function(*args, **kwargs) -> Any:
            try:
                prompt_str = prompt.format(
                    composer=composer,
                    func_spec=func_spec,
                    lang=lang,
                ).rstrip()
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
                raise AutoFuncError(
                    f"Unable to correctly parse `python` code block from the LLM response.\nPrompt:\n{prompt_str}\nResponse:\n{response}"
                ) from e
            logger.debug(f"Extracted code block:\n{code_block}")

            try:
                func = code2func(code=code_block, func_name=func_name, env=env)
                if func is None or not callable(func):
                    raise ValueError(f"No callable function '{func_name}' found in generated code")

                return func(*args, **kwargs)
            except Exception as e:
                raise AutoFuncError(f"Failed to execute generated code.\nCode:\n{code_block}\nError: {e}") from e

        return funcwrap(exec_func=autocode_function, sig_func=func_spec.to_function())

    if func_spec is not None:
        return _build_autocode(func_spec=func_spec)

    def decorator(func_spec: Union[Callable, ToolSpec]) -> Callable:
        return _build_autocode(func_spec=func_spec)

    return decorator
