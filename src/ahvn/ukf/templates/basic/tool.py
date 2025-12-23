__all__ = [
    "ToolUKFT",
    "docstring_composer",
]

from ...base import BaseUKF
from ...registry import register_ukft
from ....utils.basic.func_utils import synthesize_docstring
from ....tool.base import ToolSpec

from typing import Optional, Any, Dict, ClassVar
import asyncio


def docstring_composer(kl, **kwargs):
    """\
    Compose tool documentation from stored schemas.

    This composer generates a formatted docstring for a tool based on its
    stored input and output schemas, providing complete API documentation
    without needing the actual function code.

    Recommended Knowledge Types:
        ToolUKFT

    Args:
        kl (BaseUKF): Knowledge object containing tool schema data.
        **kwargs: Additional composition parameters (ignored).

    Returns:
        str: Synthesized docstring in Google style format.

    Example:
        >>> kl.content_resources = {
        ...     "tool_name": "add",
        ...     "description": "Add two numbers",
        ...     "input_schema": {"properties": {"a": {"type": "integer"}, ...}},
        ...     "output_schema": {"properties": {"result": {"type": "integer"}}}
        ... }
        >>> docstring_composer(kl)
        "Add two numbers\\n\\nArgs:\\n    a (int): ...\\n\\nReturns:\\n    int: ..."
    """
    resources = kl.content_resources
    return synthesize_docstring(
        description=resources.get("description", ""),
        input_schema=resources.get("input_schema", {}),
        output_schema=resources.get("output_schema", {}),
    )


@register_ukft
class ToolUKFT(BaseUKF):
    """\
    Tool class for serializing and transferring MCP server-client tool definitions.

    ToolUKFT enables server-client-based tool definitions to be stored, transferred,
    and restored across systems. It serializes all tool metadata (schemas, examples,
    client connection config) while the actual execution happens via MCP client connections.

    **IMPORTANT: Only server-client-based MCP tools are supported to become UKFT.**

    ToolUKFT is designed for tools that are served through MCP servers and accessed
    via FastMCP clients. It CANNOT serialize:
    - Regular Python functions (use ToolSpec.from_function() directly)
    - Local function-based tools with internal state
    - Tools with non-serializable closures or dependencies

    **Limitations of restored tools (from to_tool/to_atool):**

    Compared to tools created via ToolSpec.from_function(), client-based tools:
    1. **Cannot be further bound**: Binding requires access to the original function
        signature and implementation, which is only available server-side.
    2. **Cannot access internal function state**: They execute remotely via
        client.call_tool(), with no access to local variables or closures.
    3. **Cannot be serialized to code**: No function source code is available,
        only the API schema.
    4. **Require active server connection**: Must maintain connection to the
        original MCP server for execution.
    5. **Limited introspection**: Only schema information is available, no
        implementation details.

    However, client-based tools DO support:
    - Full schema information (parameters, output types, descriptions)
    - Example execution patterns
    - Both sync and async execution
    - Connection status checking

    To support binding for UKFT tools, the recommended approach is:
    - Create different ToolUKFT instances for each binding configuration
    - Store the binded ToolUKFT instances separately or as variants

    UKF Type: tool

    Recommended Components of `content_resources`:
        - tool_name (str): The name of the tool.
        - description (str): Detailed tool description.
        - input_schema (Dict): JSON Schema for input parameters (with binds applied).
        - output_schema (Dict): JSON Schema for output structure.
        - examples (List[Dict], optional): Example usage cases.
        - client_config (Dict, optional): Client connection configuration.
            - type (str): Connection type ("http", "stdio", "inmemory")
            - url (str, optional): URL for HTTP connections
            - script_path (str, optional): Python file path for stdio
            - env (Dict, optional): Environment variables for stdio
            - command (str, optional): DEPRECATED, use script_path instead
            - server (FastMCP, optional): Server instance for inmemory (cannot be serialized)

    Note: state and binds are NOT serialized because:
        1. Bind values may be arbitrary Python objects (not serializable)
        2. Serialized schemas already reflect the bound parameters
        3. Client-side ToolSpec doesn't need original binds

    Recommended Composers:
        docstring:
            Generates formatted tool documentation from schemas.
            Examples:
            ```
            Add two numbers

            Args:
                a (int): First number
                b (int): Second number (defaults to 5)

            Returns:
                int: Sum of a and b
            ```

    Example:
        >>> # Server side: Serialize ToolSpec to UKFT
        >>> tool_spec = ToolSpec.from_function(add_function)
        >>> tool_ukft = ToolUKFT.from_toolspec(
        ...     tool_spec,
        ...     client_config={"type": "http", "url": "http://server/mcp"}
        ... )
        >>>
        >>> # Transfer UKFT (e.g., save to database, send over network)
        >>> serialized = tool_ukft.model_dump_json()
        >>>
        >>> # Client side: Restore ToolSpec (client auto-created from config)
        >>> tool_ukft = ToolUKFT.model_validate_json(serialized)
        >>> tool_spec = await tool_ukft.to_atool()  # No client needed!
        >>> result = await tool_spec.acall(a=3, b=7)
        >>>
        >>> # Or pass explicit client
        >>> client = Client(...)
        >>> async with client:
        ...     tool_spec = await tool_ukft.to_atool(client)
        ...     result = await tool_spec.acall(a=3, b=7)
    """

    type_default: ClassVar[str] = "tool"

    def _create_client_from_config(self, client_config: Optional[Dict[str, Any]] = None):
        """\
        Create a FastMCP Client from configuration.

        Args:
            client_config (Dict, optional): Client configuration. Uses self.content_resources["client_config"]
                if not provided.

        Returns:
            Client: FastMCP Client instance.

        Raises:
            ValueError: If config is invalid or missing required parameters.
            NotImplementedError: If transport type is "inmemory" (requires server object).
        """
        from fastmcp import Client
        from fastmcp.client.transports import PythonStdioTransport, StreamableHttpTransport

        config = client_config or self.get("client_config", {})
        transport_type = config.get("type", "inmemory")

        if transport_type == "http":
            url = config.get("url")
            if not url:
                raise ValueError("HTTP transport requires 'url' in client_config")
            transport = StreamableHttpTransport(url=url)
            return Client(transport)

        elif transport_type == "stdio":
            script_path = config.get("script_path") or config.get("command")
            if not script_path:
                raise ValueError("STDIO transport requires 'script_path' (or 'command') in client_config")
            env = config.get("env")
            transport = PythonStdioTransport(script_path=script_path, env=env)
            return Client(transport)

        elif transport_type == "inmemory":
            # Inmemory requires a server object which cannot be serialized
            # User must provide the client explicitly
            raise NotImplementedError(
                "In-memory transport requires a server object which cannot be serialized. " "Please pass a Client instance explicitly: to_atool(client=...)"
            )

        else:
            raise ValueError(f"Unknown transport type: {transport_type}. Supported: 'http', 'stdio', 'inmemory'")

    def available(self, client=None) -> bool:
        """\
        Check if a client connection can be established to the tool's server.

        This attempts to create a client from the stored config and check basic
        connectivity requirements. It does not guarantee the tool exists on the server.

        Args:
            client: Optional FastMCP Client instance. If provided, checks this client.
                If None, attempts to create client from stored config.

        Returns:
            bool: True if client appears ready to connect, False otherwise.

        Example:
            >>> tool_ukft = ToolUKFT.model_validate_json(serialized)
            >>> if tool_ukft.available():
            ...     tool_spec = await tool_ukft.to_atool()
        """
        try:
            if client is None:
                # Try to create client from config
                try:
                    client = self._create_client_from_config()
                except (ValueError, NotImplementedError):
                    return False
            # Check if client has necessary attributes
            return hasattr(client, "list_tools") and hasattr(client, "call_tool")
        except Exception:
            return False

    @classmethod
    def from_toolspec(cls, tool_spec: ToolSpec, name: Optional[str] = None, client_config: Optional[Dict[str, Any]] = None, **updates) -> "ToolUKFT":
        """\
        Create a ToolUKFT by serializing a ToolSpec (server-side).

        This method captures all serializable information from a ToolSpec.
        The key insight: we serialize the BINDED tool (tool_spec.binded) which
        already has parameter bindings applied, avoiding the need to serialize
        potentially non-serializable bind values.

        Args:
            tool_spec (ToolSpec): The ToolSpec to serialize.
            name (str, optional): UKF name. Defaults to tool name.
            client_config (Dict, optional): Client connection configuration.
                If None, defaults to {"type": "inmemory"}.
            **updates: Additional keyword arguments to update the ToolUKFT attributes.

        Returns:
            ToolUKFT: New ToolUKFT instance with serialized tool information.

        Example:
            >>> tool_spec = ToolSpec.from_function(my_function)
            >>> tool_ukft = ToolUKFT.from_toolspec(
            ...     tool_spec,
            ...     client_config={"type": "http", "url": "http://server/mcp"}
            ... )
            >>> print(tool_ukft.text("docstring"))
        """
        # Serialize examples if present
        serialized_examples = None
        if tool_spec.examples:
            serialized_examples = [exp.to_dict() if hasattr(exp, "to_dict") else dict(exp) for exp in tool_spec.examples]

        # Serialize the BINDED tool (binds already applied to schemas)
        # This avoids serializing potentially non-serializable bind values
        content_resources = {
            "tool_name": tool_spec.binded.name,
            "description": tool_spec.binded.description,
            "input_schema": tool_spec.input_schema,  # Uses binded, so binds are already applied
            "output_schema": tool_spec.output_schema,  # Uses binded
            "examples": serialized_examples,
            "client_config": client_config or {"type": "inmemory"},
        }

        return cls(
            name=name or tool_spec.binded.name,
            content_resources=content_resources,
            content_composers={
                "default": docstring_composer,
                "docstring": docstring_composer,
            },
            **updates,
        )

    async def to_atool(self, client=None) -> ToolSpec:
        """\
        Restore a ToolSpec from ToolUKFT with a client connection (async version).

        This method reconstructs a fully functional ToolSpec using:
        1. Stored schemas for API documentation (binds already applied)
        2. Provided client (or auto-created from config) for remote execution via client.call_tool()
        3. Restored examples

        Note: Binds and state are not restored because they're already baked
        into the stored schemas. The serialized schemas already reflect the
        bound parameters.

        Args:
            client: Optional FastMCP Client instance. If None, attempts to create
                client from stored client_config. Must be within async context manager
                if provided.

        Returns:
            ToolSpec: Restored ToolSpec with remote execution capability.

        Raises:
            ValueError: If tool is not found on the server.
            NotImplementedError: If client_config uses inmemory transport (requires explicit client).

        Example:
            >>> # Auto-create client from config
            >>> tool_ukft = ToolUKFT.model_validate_json(serialized_data)
            >>> async with tool_ukft.to_atool() as tool_spec:
            ...     result = await tool_spec.acall(x=5, y=3)
            >>>
            >>> # Or provide explicit client
            >>> client = Client("http://server/mcp")
            >>> async with client:
            ...     tool_spec = await tool_ukft.to_atool(client)
            ...     result = await tool_spec.acall(x=5, y=3)
        """
        # Create client from config if not provided
        if client is None:
            client = self._create_client_from_config()

        resources = self.content_resources
        tool_name = resources["tool_name"]

        # Use the improved from_client method, but override with our stored schemas
        tool_spec = await ToolSpec.from_client(client, tool_name)

        # Override schemas with our more complete versions (which include descriptions)
        # These schemas already have binds applied from the server side
        if resources.get("input_schema"):
            tool_spec.tool.parameters = resources["input_schema"]
        if resources.get("output_schema"):
            tool_spec.tool.output_schema = resources["output_schema"]
        if resources.get("description"):
            tool_spec.tool.description = resources["description"]

        # Restore examples
        if resources.get("examples"):
            # TODO: Convert back to ExperienceType if needed
            tool_spec.examples = resources["examples"]

        # Note: state and binds are NOT restored because:
        # 1. Bind values may not be serializable
        # 2. The stored schemas already reflect the bound parameters
        # 3. The client-side ToolSpec doesn't need binds since it's already applied

        return tool_spec

    def to_tool(self, client=None) -> ToolSpec:
        """\
        Restore a ToolSpec from ToolUKFT with a client connection (sync version).

        This is a synchronous wrapper that creates a ToolSpec which manages
        client connections automatically for each call. The client connection
        is established and closed for each tool execution.

        Note: This is less efficient than async mode which can reuse connections.
        Prefer async mode (to_atool) when possible.

        Args:
            client: Optional FastMCP Client instance. If None, attempts to create
                client from stored client_config.

        Returns:
            ToolSpec: Restored ToolSpec with automatic connection management.

        Raises:
            ValueError: If tool is not found on the server.
            RuntimeError: If called from within an async context (use to_atool instead).
            NotImplementedError: If client_config uses inmemory transport (requires explicit client).

        Example:
            >>> # Auto-create client from config
            >>> tool_ukft = ToolUKFT.model_validate_json(serialized_data)
            >>> # Sync usage (NOT in async context)
            >>> tool_spec = tool_ukft.to_tool()
            >>> result = tool_spec.call(x=5, y=3)  # Auto-connects per call
            >>>
            >>> # Or provide explicit client
            >>> client = Client("http://server/mcp")
            >>> tool_spec = tool_ukft.to_tool(client)
            >>> result = tool_spec.call(x=5, y=3)
        """
        # Check if we're already in an event loop
        try:
            asyncio.get_running_loop()
            raise RuntimeError("to_tool() cannot be called from within an async context. " "Use 'await to_atool(client)' instead.")
        except RuntimeError as e:
            if "cannot be called" in str(e):
                raise
            # No running loop - continue

        # Create client from config if not provided
        if client is None:
            client = self._create_client_from_config()

        # Get tool spec using async method
        async def _get_toolspec():
            async with client:
                return await self.to_atool(client)

        tool_spec = asyncio.run(_get_toolspec())

        # Override call methods to reconnect client for each call
        # (since the client is disconnected after the async context exits)
        original_acall = tool_spec.acall

        async def sync_aware_acall(**kwargs):
            async with client:
                return await original_acall(**kwargs)

        def sync_aware_call(**kwargs):
            return asyncio.run(sync_aware_acall(**kwargs))

        tool_spec.acall = sync_aware_acall
        tool_spec.call = sync_aware_call
        tool_spec.__call__ = sync_aware_call

        return tool_spec

    @classmethod
    async def from_client(cls, client, tool_name: str, name: Optional[str] = None, client_config: Optional[Dict[str, Any]] = None, **updates) -> "ToolUKFT":
        """\
        Create a ToolUKFT by fetching and serializing a tool from an MCP server.

        This is a convenience method that combines:
        1. Fetching tool definition via client
        2. Creating ToolSpec
        3. Serializing to ToolUKFT

        Args:
            client: FastMCP Client instance (must be within async context manager).
            tool_name (str): Name of the tool to fetch from server.
            name (str, optional): UKF name. Defaults to tool_name.
            client_config (Dict, optional): Client connection configuration.
            **updates: Additional keyword arguments to update the ToolUKFT attributes.

        Returns:
            ToolUKFT: New ToolUKFT instance with tool information from server.

        Example:
            >>> client = Client("http://server/mcp")
            >>> async with client:
            ...     tool_ukft = await ToolUKFT.from_client(
            ...         client, "add",
            ...         client_config={"type": "http", "url": "http://server/mcp"}
            ...     )
        """
        # Create ToolSpec from client
        tool_spec = await ToolSpec.from_client(client, tool_name)

        # Now serialize it to UKFT
        return cls.from_toolspec(tool_spec, name=name, client_config=client_config, **updates)
