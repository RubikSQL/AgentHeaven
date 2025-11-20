"""
Unit tests for ToolUKFT.

Tests the basic functionality of ToolUKFT serialization and restoration
using in-memory transport only (no network or subprocess dependencies).
"""

import pytest
from ahvn.tool.base import ToolSpec
from ahvn.ukf.templates.basic.tool import ToolUKFT
from fastmcp import FastMCP, Client


# Test functions
def add_numbers(a: int, b: int = 5) -> str:
    """Add two numbers together.

    Args:
        a: First number
        b: Second number (default: 5)

    Returns:
        Sum as string
    """
    return str(a + b)


def greet(name: str, title: str = "Mr./Ms.") -> str:
    """Generate a greeting.

    Args:
        name: Person's name
        title: Title (default: "Mr./Ms.")

    Returns:
        Greeting message
    """
    return f"Hello, {title} {name}!"


class TestToolUKFTBasic:
    """Basic ToolUKFT functionality tests."""

    def test_from_toolspec(self):
        """Test creating ToolUKFT from ToolSpec."""
        tool_spec = ToolSpec.from_function(add_numbers)
        ukft = ToolUKFT.from_toolspec(tool_spec)

        assert ukft.type == "tool"
        assert ukft.content_resources["tool_name"] == "add_numbers"
        assert "input_schema" in ukft.content_resources
        assert "output_schema" in ukft.content_resources
        assert "description" in ukft.content_resources

    def test_serialization(self):
        """Test serialization and deserialization."""
        tool_spec = ToolSpec.from_function(add_numbers)
        ukft = ToolUKFT.from_toolspec(tool_spec)

        # Serialize
        serialized = ukft.model_dump_json()
        assert len(serialized) > 0

        # Deserialize
        restored_ukft = ToolUKFT.model_validate_json(serialized)
        assert restored_ukft.content_resources["tool_name"] == "add_numbers"
        assert restored_ukft.content_resources["description"] == tool_spec.binded.description

    def test_schema_preservation(self):
        """Test that parameter descriptions are preserved."""
        tool_spec = ToolSpec.from_function(add_numbers)
        ukft = ToolUKFT.from_toolspec(tool_spec)

        serialized = ukft.model_dump_json()
        restored_ukft = ToolUKFT.model_validate_json(serialized)

        input_schema = restored_ukft.content_resources["input_schema"]
        assert "properties" in input_schema
        assert "a" in input_schema["properties"]
        assert "description" in input_schema["properties"]["a"]

    def test_active(self):
        """Test connection check method."""
        tool_spec = ToolSpec.from_function(add_numbers)
        ukft = ToolUKFT.from_toolspec(tool_spec)

        server = FastMCP("Test Server")
        client = Client(server)

        assert ukft.available(client) is True


class TestToolUKFTAsync:
    """Async mode tests."""

    @pytest.mark.asyncio
    async def test_to_atool_basic(self):
        """Test basic async restoration and execution."""
        # Setup server
        server = FastMCP("Test Server")
        tool_spec = ToolSpec.from_function(add_numbers)
        server.add_tool(tool_spec.binded)

        # Serialize
        ukft = ToolUKFT.from_toolspec(tool_spec)
        serialized = ukft.model_dump_json()

        # Restore and execute
        client = Client(server)
        restored_ukft = ToolUKFT.model_validate_json(serialized)

        async with client:
            restored_tool = await restored_ukft.to_atool(client)

            # Test with explicit parameters
            result1 = await restored_tool.acall(a=3, b=7)
            assert result1 == "10"

            # Test with default parameter
            result2 = await restored_tool.acall(a=10)
            assert result2 == "15"

    @pytest.mark.asyncio
    async def test_to_atool_connection_check(self):
        """Test connection checking."""
        server = FastMCP("Test Server")
        tool_spec = ToolSpec.from_function(add_numbers)
        server.add_tool(tool_spec.binded)

        ukft = ToolUKFT.from_toolspec(tool_spec)
        serialized = ukft.model_dump_json()

        client = Client(server)
        restored_ukft = ToolUKFT.model_validate_json(serialized)

        async with client:
            restored_tool = await restored_ukft.to_atool(client)
            assert restored_tool.available() is True


class TestToolUKFTSync:
    """Sync mode tests."""

    def test_to_tool_basic(self):
        """Test basic sync restoration and execution."""
        # Setup server
        server = FastMCP("Test Server")
        tool_spec = ToolSpec.from_function(add_numbers)
        server.add_tool(tool_spec.binded)

        # Serialize
        ukft = ToolUKFT.from_toolspec(tool_spec)
        serialized = ukft.model_dump_json()

        # Restore and execute (sync)
        client = Client(server)
        restored_ukft = ToolUKFT.model_validate_json(serialized)

        restored_tool = restored_ukft.to_tool(client)
        result = restored_tool.call(a=7, b=3)
        assert result == "10"


class TestToolUKFTBinds:
    """Test parameter binding scenarios."""

    @pytest.mark.asyncio
    async def test_binds_not_serialized(self):
        """Test that binds are not serialized."""
        tool_spec = ToolSpec.from_function(greet)

        # Apply binds
        tool_spec.state["my_title"] = "Dr."
        tool_spec.binds["title"] = "my_title"

        # Serialize
        ukft = ToolUKFT.from_toolspec(tool_spec)
        serialized = ukft.model_dump_json()

        # Verify binds not in serialization
        import json

        data = json.loads(serialized)
        assert "state" not in data["content_resources"]
        assert "binds" not in data["content_resources"]

    @pytest.mark.asyncio
    async def test_binded_tool_execution(self):
        """Test execution with bound parameters."""
        # Setup server with bound tool
        server = FastMCP("Test Server")
        tool_spec = ToolSpec.from_function(greet)

        # Bind title to "Dr."
        tool_spec.state["my_title"] = "Dr."
        tool_spec.binds["title"] = "my_title"

        # Add binded tool to server
        server.add_tool(tool_spec.binded)

        # Serialize (binds already applied to schemas)
        ukft = ToolUKFT.from_toolspec(tool_spec)
        serialized = ukft.model_dump_json()

        # Restore and execute
        client = Client(server)
        restored_ukft = ToolUKFT.model_validate_json(serialized)

        async with client:
            restored_tool = await restored_ukft.to_atool(client)

            # Should only accept 'name' parameter (title is bound)
            result = await restored_tool.acall(name="Alice")
            assert result == "Hello, Dr. Alice!"

    @pytest.mark.asyncio
    async def test_binded_schemas(self):
        """Test that binded schemas exclude bound parameters."""
        tool_spec = ToolSpec.from_function(greet)

        # Original has 2 parameters
        original_params = tool_spec.tool.parameters["properties"]
        assert "name" in original_params
        assert "title" in original_params

        # Bind title
        tool_spec.state["my_title"] = "Dr."
        tool_spec.binds["title"] = "my_title"

        # Binded tool has 1 parameter
        binded_params = tool_spec.binded.parameters["properties"]
        assert "name" in binded_params
        assert "title" not in binded_params

        # Serialize binded version
        ukft = ToolUKFT.from_toolspec(tool_spec)
        input_schema = ukft.content_resources["input_schema"]

        # Verify only unbound parameter in schema
        assert "name" in input_schema["properties"]
        assert "title" not in input_schema["properties"]
