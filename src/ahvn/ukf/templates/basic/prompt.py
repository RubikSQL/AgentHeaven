__all__ = [
    "PromptUKFT",
    "prompt_composer",
    "prompt_list_composer",
]

from .resource import ResourceUKFT, list_composer
from ...base import ptags
from ...registry import register_ukft
from ....utils.basic.jinja_utils import load_jinja_env, create_jinja
from ....utils.basic.config_utils import hpj, HEAVEN_CM
from ....utils.basic.file_utils import exists_file, get_file_basename, has_file_ext
from ....utils.basic.hash_utils import md5hash, fmt_hash

from typing import Union, Optional, List, Dict, Any, ClassVar, Callable
from jinja2 import Environment

import tempfile

PROMPTUKFT_CREATION_TEMP_PATH = hpj(HEAVEN_CM.get("core.tmp_path", tempfile.gettempdir()), "promptukft_creation")


def prompt_composer(kl, **kwargs):
    """\
    Compose a prompt by rendering the default entry template with provided inputs.

    This composer allows a Prompt UKF instance to be called as a composer,
    automatically rendering the default entry template with the provided kwargs.
    This makes Prompt behave like a function.

    To incorporate custom logic in prompt generation, consider creating a new
    composer function instead of manually rendering the prompt each time.

    Recommended Knowledge Types:
        PromptUKFT

    Args:
        kl (BaseUKF): Knowledge object containing prompt resource data.
        **kwargs: Template variables passed to the Jinja2 template for rendering.

    Returns:
        str: Rendered prompt string.

    Example:
        >>> kl.content_resources = {
        ...     "path": "prompts/autocode",
        ...     "entry": "default.jinja"
        ... }
        >>> prompt_composer(kl, code="def add(a, b): ...", examples=[])
        "You are a skillful Python expert..."
    """
    return kl.render(**kwargs)


def prompt_list_composer(kl, ext: Union[None, str, List[str]] = "jinja;jinja2;j2;txt", **kwargs):
    return list_composer(kl, ext=ext, **kwargs)


@register_ukft
class PromptUKFT(ResourceUKFT):
    """\
    Prompt class for storing and rendering Jinja2 template folders.

    This is a specialized ResourceUKFT type designed for working with Jinja2 template
    folders that follow AgentHeaven's prompt structure (with templates, filters,
    and locale for i18n). It provides convenient methods for rendering templates
    with specified inputs and language settings.

    UKF Type: prompt
    Recommended Components of `content_resources`:
        - path (str): The original prompt folder path.
        - data (Dict[str, Optional[str]]): Serialized folder structure from serialize_path.
        - annotations (Dict[str, str]): File-level annotations for context.
        - lang (str): Default language for rendering templates (defaults to config).

    Recommended Composers:
        prompt_list:
            Lists all available .jinja templates in the prompt folder.
            Examples:
            ```
            Available templates in 'autocode':
            - default.jinja
            ```

    Example:
        >>> # Create from path
        >>> prompt = PromptUKFT.from_path("& prompts/autocode")
        >>>
        >>> # Render a template
        >>> result = prompt.render(
        ...     template="default.jinja",
        ...     code="def add(a, b): ...",
        ...     examples=[],
        ...     inputs={"a": 1, "b": 2}
        ... )
        >>> # Render with language specification
        >>> result_zh = prompt.render(
        ...     template="default.jinja",
        ...     lang="zh",
        ...     code="def add(a, b): ...",
        ...     examples=[]
        ... )
    """

    type_default: ClassVar[str] = "prompt"

    @classmethod
    def from_path(
        cls,
        path: str,
        default_entry: str = "default.jinja",
        name: Optional[str] = None,
        lang: Optional[str] = None,
        keep_path: bool = True,
        binds: Optional[Dict[str, Any]] = None,
        **updates,
    ) -> "PromptUKFT":
        """\
        Create a PromptUKFT instance from a Jinja2 template folder path.

        Serializes the prompt folder contents and configures the resource with
        appropriate metadata and composers for prompt rendering.

        Args:
            path (str): Path to the prompt folder containing .jinja templates.
            default_entry (str): The default template entry to use for prompt composer.
                Notice that entry does not limit the resource to only that template;
                other templates in the folder can still be accessed, but this will be
                the default used by prompt_composer.
                Defaults to "default.jinja".
            name (str, optional): PromptUKFT resource name. If None, generates name
                from the basename of the path. Required if path is a file.
            lang (str, optional): Default language for rendering. If None, uses
                the language from config ("prompts.lang").
            keep_path (bool): Whether to keep the original path in content_resources. Defaults to True.
            binds (Dict[str, Any], optional): Default template variables to bind.
            **updates: Additional keyword arguments to update the PromptUKFT
                instance attributes.

        Returns:
            PromptUKFT: New PromptUKFT instance with pre-configured composers:
                - prompt (default): Renders with entry template
                - list: Lists files (with ext parameter support, defaults to "jinja")
                - diagram: Shows folder structure

        Example:
            >>> prompt = PromptUKFT.from_path("& prompts/autocode")
            >>> prompt.name
            "autocode"
            >>> # Use as default composer (calls prompt_composer)
            >>> prompt.text(code="...", examples=[])
        """
        path = hpj(path, abs=True)
        if exists_file(path) and (name is None):
            raise ValueError("Name must be provided when path is a file")
        resource = ResourceUKFT.from_path(path, name=name, **updates)

        content_resources = resource.content_resources.copy()
        content_resources["lang"] = lang or content_resources.get("lang") or HEAVEN_CM.get("prompts.lang")
        content_resources["default_entry"] = default_entry or content_resources.get("default_entry") or "default.jinja"
        content_resources["binds"] = binds or content_resources.get("binds") or dict()
        if not keep_path:
            content_resources.pop("path", None)

        content_composers = {
            "default": prompt_composer,
            "prompt": prompt_composer,
            "list": prompt_list_composer,
            "diagram": resource.content_composers["diagram"],
        }

        return cls(
            name=resource.name,
            content_resources=content_resources,
            content_composers=content_composers,
            tags=resource.tags | ptags(LANGUAGE=content_resources["lang"]),
            **{k: v for k, v in resource.model_dump().items() if k not in ["name", "type", "content_resources", "content_composers", "tags"]},
        )

    @classmethod
    def from_jinja(
        cls,
        content: str,
        jinja_kwargs: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
        lang: Optional[str] = None,
        binds: Optional[Dict[str, Any]] = None,
        **updates,
    ) -> "PromptUKFT":
        """\
        Create a new PromptUKFT instance from provided jinja content).

        Args:
            content (str): Jinja2 template content string.
            name (str, optional): PromptUKFT resource name. If None, use `default` as name.
            jinja_kwargs (Dict[str, Any], optional): Additional arguments for Jinja2 template creation.
                Defaults to None, which uses an empty dictionary. These can include:
                    - `autojinja` (bool): Whether to auto-convert content to a standard Jinja2 template.
                    - `autoi18n` (bool): Whether to initialize Babel localization files.
            **updates: Additional keyword arguments to update the PromptUKFT.

        Returns:
            PromptUKFT: New PromptUKFT instance created from the provided content.

        Example:
            >>> prompt = PromptUKFT.from_jinja(
            ...     content='''\
            ... You are a helpful assistant.
            ... {% trans %}Here is the code:{% endtrans %}
            ...
            ... ```python
            ... {{ code }}
            ... ```
            ... {% trans %}Help me write tests.{% endtrans %}''',
            ...     name="simple_prompt",
            ...     lang="zh",
            ...     jinja_kwargs={
            ...         "autoi18n": True,
            ...     },
            ... )
            ... prompt.text(code="def add(a, b): return a + b")
            >>> '''\
            You are a helpful assistant.
            以下是代码：
            ```python
            def add(a, b): return a + b
            ```
            帮我编写测试。'''
        """
        content_hash = fmt_hash(md5hash(content))  # Hash by content instead of identity to allow updates
        tmp_path = hpj(PROMPTUKFT_CREATION_TEMP_PATH, content_hash, abs=True)
        create_jinja(path=tmp_path, entry="default.jinja", content=content, **(jinja_kwargs or dict()))
        return cls.from_path(path=tmp_path, default_entry="default.jinja", name=name or "default", lang=lang, binds=binds, keep_path=False, **updates)

    def bind(self, **binds) -> "PromptUKFT":
        """\
        An inplace operation to add default template variables to bind during rendering.

        Args:
            **binds: Template variables to bind as a dictionary of key-values.

        Returns:
            self: The PromptUKFT instance (for chaining).
        """
        self.content_resources["binds"] = (self.get("binds") or dict()) | binds
        return self

    def unbind(self, *keys: str) -> "PromptUKFT":
        """\
        An inplace operation to remove default template variables from binding during rendering.

        Args:
            *keys: Template variable keys to unbind.

        Returns:
            self: The PromptUKFT instance (for chaining).
        """
        binds = self.get("binds") or dict()
        for key in keys:
            binds.pop(key, None)
        self.content_resources["binds"] = binds
        return self

    def to_env(self, path: Optional[str] = None, lang: Optional[str] = None) -> Environment:
        """\
        Load the Jinja2 environment for this prompt resource.
        Notice that when path is not provided, the prompt folder is unzipped to a temporary location.
        This could result in missing files if the temporary folder is cleaned up, use with caution.
        TODO: Add locking mechanism to avoid cleanup during usage.

        Args:
            path (str, optional): Path to the prompt folder containing .jinja templates.
            lang (str, optional): Language code for this rendering. If None, uses
                the default language from content_resources or config.

        Returns:
            Environment: Jinja2 Environment object for rendering templates.
        """
        lang = lang or self.get("lang")
        with self(path=path, overwrite=False, cleanup=False) as temp_path:
            try:
                env = load_jinja_env(temp_path, lang=lang)
            except Exception as e:
                raise ValueError(f"Failed to load Jinja2 environment for prompt at path: {temp_path}. It may have been corrupted. Error: {e}.")
            return env

    def render(self, path: Optional[str] = None, entry: Optional[str] = None, lang: Optional[str] = None, **kwargs) -> str:
        """\
        Render a template from this prompt resource with the given inputs.

        This is the main method for using PromptUKFT resources. It loads the
        appropriate Jinja2 environment, retrieves the specified template,
        and renders it with the provided keyword arguments.

        Args:
            path (str, optional): Path to the prompt folder containing .jinja templates.
            entry (str): Default template to use for prompt composer.
                Defaults to None, which falls back to the "default_entry" in content_resources.
            name (str, optional): PromptUKFT resource name. If None and path is a directory, generates name
                from the basename of the path. Required if path is a file.
            lang (str, optional): Language code for this rendering. If None, uses
                the default language from content_resources or config.
            **kwargs: Template variables passed to the Jinja2 template for rendering.

        Returns:
            str: Rendered template string.

        Raises:
            ValueError: If the prompt resource has no path specified.
            TemplateNotFound: If the specified template entry file doesn't exist.

        Example:
            >>> prompt = PromptUKFT.from_path("& prompts/autocode")
            >>> result = prompt.render(
            ...     code="def add(a, b): return a + b",
            ...     examples=[{"inputs": {"a": 1, "b": 2}, "output": 3}],
            ...     hints=["Use simple arithmetic"]
            ... )
        """
        entry = entry or self.get("default_entry") or "default.jinja"
        lang = lang or self.get("lang") or HEAVEN_CM.get("prompts.lang")
        env = self.to_env(path=path, lang=lang)
        tmpl = env.get_template(name=entry)
        binds = self.get("binds") or dict()
        return tmpl.render(**(binds | kwargs))

    def format(self, composer: Optional[Union[str, Callable]] = "default", **kwargs) -> str:
        return self.text(composer=composer, **kwargs)

    def list_templates(self) -> List[str]:
        """\
        List all available .jinja template files in this prompt resource.

        Returns:
            List[str]: Sorted list of template filenames (excluding files starting with '_').

        Example:
            >>> prompt = PromptUKFT.from_path("& prompts/autocode")
            >>> prompt.list_templates()
            ['default.jinja']
        """
        return self.to_env().list_templates(filter_func=lambda x: (not get_file_basename(x).startswith("_")) and has_file_ext(x, ext="jinja;jinja2;j2;txt"))
