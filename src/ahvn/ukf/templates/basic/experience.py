__all__ = [
    "ExperienceUKFT",
    "ExperienceType",
    "assertion_composer",
    "instance_prompt_composer",
]

from ...base import BaseUKF
from ...registry import register_ukft
from ....cache import CacheEntry
from ....utils.basic.jinja_utils import load_jinja_env
from ....utils.basic.config_utils import hpj

from typing import Union, Dict, Any, ClassVar


def assertion_composer(kl, **kwargs):
    """\
    Compose a Python-like assertion string for testing function outputs.

    Generates assertion strings in the format "assert (func(args) == expected_output)"
    based on the knowledge object's content resources. Useful for creating test cases
    and validation statements from experience data.

    Recommended Knowledge Types:
        ExperienceUKFT

    Args:
        kl (BaseUKF): Knowledge object containing func, inputs, and output data.
        **kwargs: Optional keyword arguments to override content_resources:
            - func (str): Function name to test.
            - inputs (Dict): Function input arguments.
            - output (Any): Expected function output.
            - expected (Any): Alternative expected output (takes precedence over output).

    Returns:
        str: Formatted assertion string for testing.

    Example:
        >>> kl.content_resources = {"func": "add", "inputs": {"a": 1, "b": 2}, "output": 3}
        >>> assertion_composer(kl)
        "assert (add(a=1, b=2) == 3)"
    """
    func = kwargs.get("func", kl.get("func", ""))
    inputs = kwargs.get("inputs", kl.get("inputs", dict()))
    output = kwargs.get("output", kl.get("output", ...))
    expected = kwargs.get("expected", kl.get("expected", ...))
    if expected is not ...:
        output = kwargs.get("expected", kl.get("expected", output))
    args = ", ".join(f"{p}={repr(a)}" for p, a in inputs.items())
    return f"assert ({func}({args}) == {repr(output)})"


def instance_prompt_composer(kl, lang=None, env=None, template="default_instance.jinja", **kwargs):
    """\
    Compose dynamic prompts using Jinja2 templates with experience data.

    Renders Jinja2 templates using content resources from the knowledge object,
    enabling dynamic prompt generation for AI interactions. Combines template
    rendering with experience data for context-aware content generation.

    Recommended Knowledge Types:
        ExperienceUKFT

    Args:
        kl (BaseUKF): Knowledge object containing template context data.
        lang (str, optional): Language setting for Jinja2 environment.
        env (str, optional): Path to Jinja2 template environment.
            Defaults to "& prompts/experience" (in the ahvn resources folder).
        template (str, optional): Template filename.
            "default_instance.jinja" generates a prompt containing inputs, output, expected and hints.
            "correct_instance.jinja" generates a prompt containing inputs, expected as output, and hints
            Defaults to "default_instance.jinja".
        **kwargs: Additional context variables for template rendering,
            override content_resources values.

    Returns:
        str: Rendered prompt string from the template.

    Example:
        >>> kl.content_resources = {"func": "calculate", "inputs": {"x": 5}, "output": 20, "expected": 25}
        >>> kl.text(instance_prompt_composer, lang='en')
        Inputs:
        - x: 5
        Output:
        - 20
        Expected:
        - 25
    """
    env = env or hpj("& prompts/experience")
    return load_jinja_env(env, lang=lang).get_template(template).render(kl.content_resources | kwargs)


@register_ukft
class ExperienceUKFT(BaseUKF):
    """\
    Experience class storing function inputs-output pairs.

    UKF Type: experience
    Recommended Components of `content_resources`:
        - func (str): The name of the generator of this experience instance.
        - inputs (Dict): The inputs.
        - output (Any): The output.
        - expected (Any): The ground-truth output.
        - hints (List[str]): Optional hints or notes about the experience instance.
        - metatdata (Dict): Any extra information related to the experience instance.

    Recommended Composers:
        assert:
            Examples:
            ```
            assert (add(a=1,b=2) == 3)
            ```
        instance:
            Examples:
            ```
            Inputs:
            - a: 1
            - b: 2
            Output:
            - 3
            ```
    """

    type_default: ClassVar[str] = "experience"

    @classmethod
    def from_cache_entry(cls, entry: Union[Dict, CacheEntry], name=None, **updates):
        """\
        Create an ExperienceUKFT instance from a cache entry or dictionary.

        Provides convenient construction from cached function call data,
        automatically setting up content resources and composers for common
        experience management patterns.

        Args:
            entry (Union[Dict, CacheEntry]): Cache entry or dictionary containing
                experience data. CacheEntry objects are converted using to_dict().
            name (str, optional): Experience name. If None, generates name from
                function name and input parameters in "func(param=value)" format.
            **updates: Additional keyword arguments to update the Experience
                instance attributes.

        Returns:
            ExperienceUKFT: New ExperienceUKFT instance with pre-configured composers:
                - default/instance: instance_prompt_composer for structured prompts
                - assertion: assertion_composer for test generation

        Example:
            >>> cache_entry = CacheEntry(func="add", inputs={"a": 1, "b": 2}, output=3)
            >>> exp = ExperienceUKFT.from_cache_entry(cache_entry)
            >>> exp.name
            "add(a=1, b=2)"
            >>> exp.text("assertion")
            "assert (add(a=1, b=2) == 3)"
        """
        return cls(
            name=(name if name is not None else f"{entry.func}(" + (", ".join(f"{p}={repr(a)}" for p, a in entry.inputs.items())) + ")"),
            content_resources=(entry.to_dict() if isinstance(entry, CacheEntry) else dict(entry)) | updates.get("content_resources", dict()).copy(),
            content_composers={
                "default": instance_prompt_composer,
                "instance": instance_prompt_composer,
                "assertion": assertion_composer,
            },
            **{k: v for k, v in updates.items() if k != "content_resources"},
        )

    def to_cache_entry(self, **updates) -> CacheEntry:
        """\
            Convert the ExperienceUKFT instance to a CacheEntry.

        Extracts relevant fields from the ExperienceUKFT's content resources
        to create a CacheEntry object, facilitating interoperability with
        caching mechanisms.

        Returns:
            CacheEntry: A CacheEntry object populated with the ExperienceUKFT's
                function name, inputs, and output.
            **updates: Additional keyword arguments to update the CacheEntry attributes.

        Example:
            >>> exp = ExperienceUKFT(name="exp", content_resources={"func": "add", "inputs": {"a": 1, "b": 2}, "output": 3})
            >>> cache_entry = exp.to_cache_entry()
            >>> cache_entry.func
            "add"
            >>> cache_entry.inputs
            {"a": 1, "b": 2}
            >>> cache_entry.output
            3
        """
        return CacheEntry.from_dict(self.content_resources | updates)

    def annotate(self, expected: Any = ..., **updates) -> "ExperienceUKFT":
        """\
        Annotates the ExperienceUKFT with expected output and metadata.

        Creates a clone of the ExperienceUKFT with the expected value and metadata updated
        in the content_resources. This allows for adding ground-truth labels or
        annotations to existing experience data.

        Args:
            expected (Any): The expected output of the function. If omitted (...),
                will use the actual output as annotation.
            **updates: Additional keyword arguments to update the ExperienceUKFT instance attributes.

        Returns:
            ExperienceUKFT: A new ExperienceUKFT instance with the annotation.

        Example:
            >>> exp = ExperienceUKFT(content_resources={"func": "add", "inputs": {"a": 1, "b": 2}, "output": 3})
            >>> annotated_exp = exp.annotate(expected=5, metadata={"verified": True})
            >>> annotated_exp.content_resources["expected"]
            5
            >>> annotated_exp.metadata["verified"]
            True
        """
        if expected is ...:
            expected = self.get("output")
        content_resources = self.content_resources | updates.get("content_resources", dict()) | {"expected": expected}
        return self.clone(**(updates | {"content_resources": content_resources}))

    @property
    def inputs(self) -> Dict[str, Any]:
        """Get the inputs from content_resources."""
        return self.get("inputs", dict())

    @property
    def output(self) -> Any:
        """Get the output from content_resources."""
        return self.get("output", None)


ExperienceType = Union[Dict[str, Any], ExperienceUKFT, CacheEntry]
