from __future__ import annotations

__all__ = [
    "ToolSpec",
]

from ..utils.basic.func_utils import (
    parse_docstring as parse_docstring_to_spec,
    code2func,
    synthesize_docstring,
    synthesize_def,
    synthesize_signature,
    funcwrap,
)
from ..utils.basic.jinja_utils import load_jinja_env
from ..utils.basic.config_utils import dsetdef, dget

from typing import Union, Optional, Callable, Iterable, Dict, List, Any, TYPE_CHECKING

from copy import deepcopy
import asyncio
import functools

if TYPE_CHECKING:
    from ..ukf.templates.basic.experience import ExperienceType
    from mcp.types import Tool as MCPTool
    from fastmcp.tools import Tool as FastMCPTool


class ToolSpec(object):
    """\
    A specification wrapper for tools that can be used with LLMs.

    ToolSpec can be used as a decorator to convert functions into tool specifications:

    Example:
        >>> @ToolSpec(name="add", description="Add two numbers")
        ... def add(a: int, b: int) -> int:
        ...     return a + b
        >>> result = add(a=3, b=5)  # Still works as a function
        8
        >>> llm.tooluse("Add 3 and 5", tools=[add])  # Works as a tool
    """

    def __new__(cls, *args, **kwargs):
        """\
        Create a new ToolSpec instance or return a decorator.

        When called with keyword arguments (e.g., @ToolSpec(name="add")),
        returns a decorator that creates a ToolSpec from the decorated function.

        When called with no arguments, returns a normal ToolSpec instance.
        """
        # If called with no arguments, create a normal instance
        if not args and not kwargs:
            instance = super().__new__(cls)
            return instance

        # If called with keyword arguments, return a decorator
        def decorator(func: Callable) -> "ToolSpec":
            return cls.from_function(func, *args, **kwargs)

        return decorator

    def __init__(self):
        # Skip initialization if this is being used as a decorator
        # (in that case, __new__ returns a function, not a ToolSpec instance)
        if not isinstance(self, ToolSpec):
            return
        self.tool: FastMCPTool = None
        self.state: Dict[str, Any] = dict()
        self.binds: Dict[str, str] = dict()
        self.examples: Optional[Iterable[ExperienceType]] = None
        self._clear_cache()

    def _clear_cache(self):
        self._binded: FastMCPTool = None
        self._params: Dict[str, Any] = None
        self._signature: str = None
        self._code: str = None
        self._docstring: str = None
        self._env: Any = None
        self._template: Any = None

    @property
    def name(self):
        return self.tool.name

    @property
    def binded(self):
        if not self.binds:
            return self.tool
        if self._binded is not None:
            return self._binded
        from fastmcp.tools import Tool as FastMCPTool
        from fastmcp.tools.tool_transform import ArgTransform

        self._binded = FastMCPTool.from_tool(
            tool=self.tool, transform_args={k: ArgTransform(hide=True, default=dget(self.state, v)) for k, v in self.binds.items()}
        )
        return self._binded

    @property
    def input_schema(self):
        if self._params is not None:
            return self._params
        self._params = deepcopy(self.binded.parameters)
        if "required" not in self._params:
            properties = self._params.get("properties", {})
            self._params = self._params | {
                "required": [k for k, v in properties.items() if "default" not in v],
            }
        return self._params

    @property
    def params(self):
        return self.input_schema.get("properties", {})

    @property
    def output_schema(self):
        return self.binded.output_schema

    async def aexec(self, **kwargs):
        """\
        Execute the tool asynchronously with the provided keyword arguments, returning the full structured content.

        Args:
            **kwargs: The keyword arguments to pass to the tool.

        Returns:
            ToolResult. The full structured content.
        """
        return await self.binded.run(arguments=kwargs)

    def exec(self, **kwargs):
        """\
        Execute the tool synchronously with the provided keyword arguments, returning the full structured content.

        Args:
            **kwargs: The keyword arguments to pass to the tool

        Returns:
            ToolResult. The full structured content.
        """
        return asyncio.run(self.binded.run(arguments=kwargs))

    async def acall(self, **kwargs):
        """\
        Execute the tool asynchronously with the provided keyword arguments, returning the main output value.

        Args:
            **kwargs: The keyword arguments to pass to the tool

        Returns:
            Any. The main output value.
        """
        result = await self.aexec(**kwargs)
        if len(self.binded.output_schema.get("properties", {})) == 1:
            return result.structured_content[next(iter(self.binded.output_schema.get("properties", {})))]
        return result.structured_content

    def call(self, **kwargs):
        """\
        Execute the tool synchronously with the provided keyword arguments, returning the main output value.

        Args:
            **kwargs: The keyword arguments to pass to the tool

        Returns:
            Any. The main output value.
        """
        result = self.exec(**kwargs)
        if len(self.binded.output_schema.get("properties", {})) == 1:
            return result.structured_content[next(iter(self.binded.output_schema.get("properties", {})))]
        return result.structured_content

    def __call__(self, **kwargs):
        return self.call(**kwargs)

    def available(self) -> bool:
        """\
        Check if this ToolSpec has an active MCP client connection.

        This is useful for ToolSpecs created via from_client() to verify
        the connection is still active before attempting remote calls.

        Returns:
            bool: True if connected to an MCP server, False otherwise.
                    For local tools (from_function), always returns True.

        Example:
            >>> spec = await ToolSpec.from_client(client, "add")
            >>> if spec.available():
            ...     result = await spec.acall(a=3, b=7)
        """
        # Check if this is a remote tool with client
        client = self.state.get("_mcp_client")
        if client is None:
            # Local tool, always "connected"
            return True

        # Check if client has an active session
        try:
            return client.session is not None
        except (AttributeError, RuntimeError):
            return False

    @classmethod
    def from_function(
        cls,
        func: Callable,
        examples: Optional[Iterable[ExperienceType]] = None,
        parse_docstring: bool = True,
        *args,
        **kwargs,
    ) -> "ToolSpec":
        """\
        Create a ToolSpec from a Python function.

        Args:
            func (Callable): The Python function or callable class instance to convert into a tool.
                If a class instance with a __call__ method is provided, that method will be used.
            examples (Optional[Iterable[ExperienceType]], optional): Example usages of the tool. Defaults to None.
            parse_docstring (bool, optional): Whether to parse the function's docstring for description. Defaults to True.
            *args: Additional positional arguments to pass to FastMCPTool.from_function.
            **kwargs: Additional keyword arguments to pass to FastMCPTool.from_function.

        Returns:
            ToolSpec: An instance of ToolSpec wrapping the provided function.
        """
        from fastmcp.tools import Tool as FastMCPTool

        tool_spec = cls()
        func_spec = deepcopy(kwargs)
        docstring_spec = None

        if (not callable(type(func))) and hasattr(func, "__call__"):
            actual_func = func.__call__
        else:
            actual_func = func

        if parse_docstring:
            docstring_spec = parse_docstring_to_spec(actual_func)

        if docstring_spec:
            description = docstring_spec.get("description")
            if (not func_spec.get("description")) and description:
                func_spec["description"] = description
            returns = docstring_spec.get("returns")
            if (not func_spec.get("output_schema")) and returns:
                func_spec["output_schema"] = returns

        if (not kwargs.get("output_schema")) and (func_spec.get("output_schema")):
            # The original function does not have output schema, but we got one from docstring parsing
            # We need to wrap the function return value to match the output schema
            @functools.wraps(actual_func)
            def wrapper(*fargs, **fkwargs):
                return {"result": actual_func(*fargs, **fkwargs)}

            tool_spec.tool = FastMCPTool.from_function(fn=wrapper, *args, **func_spec)
        else:
            tool_spec.tool = FastMCPTool.from_function(fn=actual_func, *args, **func_spec)

        if docstring_spec:
            parsed = docstring_spec.get("args", {}).get("properties", {})
            if parsed:
                schema = deepcopy(tool_spec.tool.parameters or {})
                if not schema:
                    schema = {"type": "object", "properties": {}}
                properties = schema.setdefault("properties", {})
                for param_name, param_schema in list(properties.items()):
                    if param_name in parsed:
                        properties[param_name] = parsed[param_name] | param_schema
                tool_spec.tool.parameters = schema

        tool_spec.examples = examples
        return tool_spec

    @classmethod
    def from_mcp(
        cls,
        tool: Union[MCPTool, FastMCPTool],
        examples: Optional[Iterable[ExperienceType]] = None,
        *args,
        **kwargs,
    ) -> "ToolSpec":
        """\
        Create a ToolSpec from an MCP Tool.

        Args:
            tool (Union[MCPTool, FastMCPTool]): The MCP Tool to convert into a ToolSpec.
            examples (Optional[Iterable[ExperienceType]], optional): Example usages of the tool. Defaults to None.
            *args: Additional positional arguments to pass to FastMCPTool.from_tool.
            **kwargs: Additional keyword arguments to pass to FastMCPTool.from_tool.

        Returns:
            ToolSpec: An instance of ToolSpec wrapping the provided MCP tool.
        """
        from fastmcp.tools import Tool as FastMCPTool

        tool_spec = cls()
        tool_spec.tool = FastMCPTool.from_tool(tool=tool, *args, **kwargs)
        tool_spec.examples = examples
        return tool_spec

    @classmethod
    async def from_client(
        cls,
        client,
        tool_name: str,
        examples: Optional[Iterable[ExperienceType]] = None,
        *args,
        **kwargs,
    ) -> "ToolSpec":
        """\
        Create a ToolSpec from a FastMCP Client by retrieving a tool from an MCP server.

        This method connects to an MCP server via the provided client, retrieves the
        specified tool's definition, and creates a ToolSpec that can call the remote tool.

        Args:
            client: FastMCP Client instance (must be within an async context manager).
            tool_name (str): The name of the tool to retrieve from the server.
            examples (Optional[Iterable[ExperienceType]], optional): Example usages of the tool. Defaults to None.
            *args: Additional positional arguments (ignored for client-based tools).
            **kwargs: Additional keyword arguments (ignored for client-based tools).

        Returns:
            ToolSpec: An instance of ToolSpec wrapping the remote tool.

        Raises:
            ValueError: If the specified tool is not found on the server.
            RuntimeError: If the client is not connected.

        Example:
            >>> from fastmcp import FastMCP, Client
            >>> server = FastMCP("test")
            >>> @server.tool()
            >>> def add(a: int, b: int = 5) -> int:
            ...     return a + b
            >>> client = Client(server)
            >>> async with client:
            ...     spec = await ToolSpec.from_client(client, "add")
            ...     result = spec.call(a=3, b=7)
            ...     print(result)  # 10
        """
        from fastmcp.tools import Tool as FastMCPTool

        # List all available tools from the server
        tools = await client.list_tools()

        # Find the requested tool
        mcp_tool = None
        for tool in tools:
            if tool.name == tool_name:
                mcp_tool = tool
                break

        if mcp_tool is None:
            available = [t.name for t in tools]
            raise ValueError(f"Tool '{tool_name}' not found on server. Available tools: {available}")

        # Extract schema information
        input_schema = mcp_tool.inputSchema if hasattr(mcp_tool, "inputSchema") else {}
        output_schema = mcp_tool.outputSchema if hasattr(mcp_tool, "outputSchema") else {}
        description = mcp_tool.description or ""

        # Create a simple placeholder function
        async def placeholder():
            pass

        # Create ToolSpec with placeholder, then override schemas
        tool_spec = cls()
        tool_spec.tool = FastMCPTool.from_function(
            fn=placeholder,
            name=mcp_tool.name,
            description=description,
        )

        # Override parameters and output_schema with actual MCP schemas
        if input_schema:
            tool_spec.tool.parameters = input_schema
        if output_schema:
            tool_spec.tool.output_schema = output_schema

        # Store client reference for execution
        tool_spec.state["_mcp_client"] = client
        tool_spec.state["_mcp_tool_name"] = tool_name

        # Override the call methods to use the client directly
        async def client_acall(**kwargs):
            result = await client.call_tool(tool_name, kwargs)
            # Extract the actual value from the result
            if hasattr(result, "structured_content") and result.structured_content:
                structured = result.structured_content
                # If single-key dict with 'result', unwrap it
                if isinstance(structured, dict) and len(structured) == 1 and "result" in structured:
                    return structured["result"]
                return structured
            if result.content and len(result.content) > 0:
                text = result.content[0].text
                try:
                    if "." in text:
                        return float(text)
                    return int(text)
                except (ValueError, AttributeError):
                    return text
            return None

        tool_spec.acall = client_acall

        def client_call(**kwargs):
            # Try to get the current running loop
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    # We are in a running loop. We cannot use asyncio.run().
                    # And we cannot block this loop waiting for a thread that tries to run another loop
                    # if the client is bound to this loop.
                    # The best we can do is warn the user or try to use nest_asyncio if available.
                    try:
                        import nest_asyncio

                        nest_asyncio.apply(loop)
                        return loop.run_until_complete(client_acall(**kwargs))
                    except ImportError:
                        raise RuntimeError(
                            "Cannot call async tool synchronously from a running event loop. "
                            "Please use 'await tool.acall(...)' instead, or install 'nest_asyncio' "
                            "and apply it to the loop."
                        )
            except RuntimeError:
                # No running loop, safe to use asyncio.run()
                return asyncio.run(client_acall(**kwargs))

        tool_spec.call = client_call
        tool_spec.__call__ = client_call

        tool_spec.examples = examples
        return tool_spec

    @classmethod
    def from_code(
        cls,
        code: str,
        func_name: Optional[str] = None,
        env: Optional[Dict] = None,
        examples: Optional[Iterable[ExperienceType]] = None,
        *args,
        **kwargs,
    ) -> "ToolSpec":
        """\
        Create a ToolSpec from a code snippet.

        Args:
            code (str): The code snippet containing the function definition.
            func_name (Optional[str], optional): The name of the function to extract from the code. Defaults to None.
                If None, and only one callable is found, that function will be used.
                Notice that `func_name` is NOT the same as `name`, which will be used as the function name in the tool spec.
                `func_name` only helps to identify which function to use from the code snippet, it does NOT affect the tool spec.
            env (Optional[Dict], optional): The environment in which to execute the code. Defaults to None.
            examples (Optional[Iterable[ExperienceType]], optional): Example usages of the tool. Defaults to None.
            *args: Additional positional arguments to pass to `FastMCPTool.from_function`.
            **kwargs: Additional keyword arguments to pass to `FastMCPTool.from_function`.

        Returns:
            ToolSpec: An instance of ToolSpec wrapping the function defined in the provided code.
        """
        return cls.from_function(func=code2func(code=code, func_name=func_name, env=env), examples=examples, *args, **kwargs)

    def bind(self, param: str, state_key: Optional[str] = None, default: Optional[Any] = None) -> "ToolSpec":
        """\
        Bind a parameter to a state key (and a value if the key is not present).
        The benefit of using a `state` instead of a direct value is that the state can be
        updated externally, and the tool will always use the latest value from the state.

        Args:
            param (str): The parameter name to bind.
            state_key (Optional[str]): The dot-separated state key path to bind the parameter to.
                It supports nested keys using dot notation (e.g., "user.age").
                If None, the parameter name will be used as the state key. Defaults to None.
            default: The default value if the state key is not present. Defaults to None.

        Returns:
            ToolSpec: The ToolSpec instance (for chaining).
        """
        dsetdef(self.state, state_key or param, default)
        self.binds[param] = state_key or param
        self._clear_cache()  # Invalidate the cached binded tool
        return self

    def unbind(self, param: str) -> "ToolSpec":
        """\
        Unbind a parameter from its state key.

        Args:
            param (str): The parameter name to unbind.

        Returns:
            ToolSpec: The ToolSpec instance (for chaining).
        """
        self.binds.pop(param, None)
        self._clear_cache()  # Invalidate the cached binded tool
        return self

    def clone(self) -> "ToolSpec":
        new_tool = ToolSpec()
        new_tool.tool = self.tool
        # Copy call interfaces correctly
        new_tool.exec = self.exec
        new_tool.aexec = self.aexec
        new_tool.call = self.call
        new_tool.acall = self.acall
        # Preserve examples and binds using deep copy to avoid shared mutation
        new_tool.examples = deepcopy(self.examples) if self.examples is not None else None
        new_tool.binds = deepcopy(self.binds)
        # State is propagated (shallow copy) to preserve shared resources like clients
        new_tool.state = self.state.copy()
        # Invalidate any cached binded tool so the clone computes its own cache
        new_tool._clear_cache()
        return new_tool

    def to_fastmcp(self) -> FastMCPTool:
        return self.binded.copy()

    def to_mcp(self) -> MCPTool:
        return self.binded.copy().to_mcp_tool()

    def to_jsonschema(self, **kwargs):
        return {
            "type": "function",
            "function": {
                "name": self.binded.name,
                "description": self.binded.description,
                "parameters": self.input_schema,
                # Note: strict mode disabled due to compatibility issues with Optional parameters
                # "strict": True,
            }
            | kwargs,
        }

    @property
    def docstring(self):
        """\
        Generate and return a synthesized docstring from the tool specification.

        Returns:
            str: The synthesized docstring in Google style format.
        """
        if self._docstring is not None:
            return self._docstring
        self._docstring = synthesize_docstring(
            description=self.binded.description,
            input_schema=self.input_schema,
            output_schema=self.output_schema,
            # examples=self.examples,
        )
        return self._docstring

    @property
    def code(self):
        """\
        Generate a complete Python function definition with synthesized docstring.

        Returns:
            str: The complete function code including signature, docstring, and placeholder body.
        """
        if self._code is not None:
            return self._code
        self._code = synthesize_def(
            name=self.binded.name,
            docstring=self.docstring,
            input_schema=self.input_schema,
            output_schema=self.output_schema,
            code="pass",
        )
        return self._code

    def to_function(self):
        """\
        Return a function that behaves like `ToolSpec.__call__` but has the same signature as the string produced by `ToolSpec.code`.

        Returns:
            Callable: The generated function.
        """
        try:
            func = code2func(code=self.code, func_name=self.binded.name)
            return funcwrap(exec_func=self.__call__, sig_func=func)
        except Exception as e:
            raise RuntimeError(f"Failed to convert ToolSpec to function.\nCode:\n{self.code}\nError: {e}") from e

    def signature(self, **kwargs) -> Optional[Iterable[ExperienceType]]:
        """\
        Generate a tool function call signature with provided keyword arguments (and default values for missing arguments).

        Args:
            **kwargs: The keyword arguments to include in the function call signature.

        Returns:
            str: The function call signature as a string.
        """
        return synthesize_signature(
            name=self.binded.name,
            input_schema=self.input_schema,
            arguments=kwargs,
        )

    def to_prompt(self):
        if self._env is None:
            self._env = load_jinja_env("& prompts/system/", lang="en")
        if self._template is None:
            self._template = self._env.get_template("toolspec.jinja")
        docstring = self.docstring
        rendered = self._template.render(
            signature=self.signature(),
            docstring=docstring.strip() if isinstance(docstring, str) else docstring,
        )
        return rendered

    def to_ukf(self):
        raise NotImplementedError
