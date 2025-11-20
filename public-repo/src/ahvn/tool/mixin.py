__all__ = [
    "reg_toolspec",
    "ToolRegistry",
]

from typing import List, Dict, Optional, Iterable
from .base import ToolSpec


def reg_toolspec(func=None, examples: Optional[Iterable] = None, parse_docstring: bool = True, *args, **kwargs):
    """\
    Decorator to mark a method as a tool that should be registered as a ToolSpec.

    This decorator can be used with or without arguments:
    - @reg_toolspec
    - @reg_toolspec(parse_docstring=True, description="Custom description")

    The ToolSpec is created when `to_toolspecs()` is called on an instance.

    Args:
        func (Optional[Callable], optional):
            The function to decorate. If None, returns a partial decorator. Defaults to None.
        examples (Optional[Iterable[ExperienceType]], optional): Example usages of the tool. Defaults to None.
        parse_docstring (bool, optional): Whether to parse the function's docstring for description. Defaults to True.
        *args: Additional positional arguments to pass to FastMCPTool.from_function.
        **kwargs: Additional keyword arguments to pass to FastMCPTool.from_function.

    Returns:
        Callable: The decorated function with tool metadata attached.

    Example:
        ```python
        class MyKLBase(ToolRegistry):
            @reg_toolspec(parse_docstring=True)
            def search(self, query: str) -> str:
                \"\"\"Search for items.

                Args:
                    query: The search query string.

                Returns:
                    str: The search results.
                \"\"\"
                return f"Results for: {query}"
        ```
    """

    def decorator(f):
        f._is_toolspec = True
        f._toolspec_args = args
        f._toolspec_kwargs = {"examples": examples, "parse_docstring": parse_docstring, **kwargs}
        return f

    if func is None:
        return decorator
    else:
        return decorator(func)


class ToolRegistry:
    """\
    A mixin class that provides tool registration and management capabilities.

    This class uses `__init_subclass__` to automatically detect and register methods decorated
    with `@reg_toolspec` during class definition, storing the metadata for later ToolSpec creation.

    The `@reg_toolspec` decorator is automatically available as a class method on any subclass.

    Example:
        ```python
        class MyCustomKLBase(KLBase):
            @reg_toolspec(parse_docstring=True)
            def search(self, query: str) -> str:
                \"\"\"Search for items.

                Args:
                    query: The search query string.

                Returns:
                    str: The search results.
                \"\"\"
                return f"Results for: {query}"

        # ToolSpecs are created when to_toolspecs() is called
        kb = MyCustomKLBase()
        tools = kb.to_toolspecs()  # Creates and returns ToolSpec instances
        ```
    """

    _toolspecs: Dict[str, dict] = {}

    def __init_subclass__(cls, **kwargs):
        """\
        Called when a subclass is created. Scans for decorated methods and stores their metadata.
        """
        super().__init_subclass__(**kwargs)
        cls._toolspecs = {}
        for func_name, func in cls.__dict__.items():
            if func_name.startswith("_"):
                continue
            if hasattr(func, "_is_toolspec") and func._is_toolspec and callable(func):
                toolspec_args = getattr(func, "_toolspec_args", ())
                toolspec_kwargs = getattr(func, "_toolspec_kwargs", {})
                cls._toolspecs[func_name] = {"func": func, "args": toolspec_args, "kwargs": toolspec_kwargs}

    def toolspec(self, name: str) -> ToolSpec:
        toolspec = ToolSpec.from_function(
            func=self.__class__._toolspecs[name]["func"],
            *self.__class__._toolspecs[name]["args"],
            **self.__class__._toolspecs[name]["kwargs"],
        )
        toolspec.bind(param="self", state_key=None, default=self)
        return toolspec

    def to_toolspecs(self) -> Dict[str, ToolSpec]:
        """\
        Collect all methods decorated with @reg_toolspec and convert them to ToolSpec instances.

        This method creates ToolSpec instances from the registered tool metadata, binding 'self'
        to each tool so they can be called as instance methods.

        Returns:
            Dict[ToolSpec]: A named list of ToolSpec instances for all decorated methods.
        """
        toolspecs = {}
        for name, spec in self.__class__._toolspecs.items():
            toolspecs[name] = ToolSpec.from_function(func=spec["func"], *spec["args"], **spec["kwargs"])
            toolspecs[name].bind(param="self", state_key=None, default=self)
        return toolspecs

    def list_toolspecs(self) -> List[str]:
        """\
        List the names of all methods decorated with @reg_toolspec.

        Returns:
            List[str]: A list of method names that are registered as tools.
        """
        return list(self.__class__._toolspecs.keys())
