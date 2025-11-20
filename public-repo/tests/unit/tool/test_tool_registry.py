"""\
Unit tests for the ToolRegistry mixin and @reg_toolspec decorator.
"""

import pytest
from typing import List

from ahvn.tool import ToolSpec, ToolRegistry, reg_toolspec
from ahvn.klbase import KLBase
from ahvn.klengine import BaseKLEngine
from ahvn.klstore import BaseKLStore


class TestToolspecDecorator:
    """Test the @reg_toolspec decorator."""

    def test_decorator_without_args(self):
        """Test that @reg_toolspec works without arguments."""

        class TestClass(ToolRegistry):
            @reg_toolspec
            def test_method(self, x: int) -> int:
                """Test method.

                Args:
                    x: An integer.

                Returns:
                    int: The same integer.
                """
                return x

        obj = TestClass()
        assert hasattr(obj.test_method.__func__, "_is_toolspec")
        assert obj.test_method.__func__._is_toolspec is True

    def test_decorator_with_args(self):
        """Test that @reg_toolspec works with arguments."""

        class TestClass(ToolRegistry):
            @reg_toolspec(parse_docstring=False, description="Custom description")
            def test_method(self, x: int) -> int:
                return x

        obj = TestClass()
        assert hasattr(obj.test_method.__func__, "_is_toolspec")
        assert obj.test_method.__func__._toolspec_kwargs["parse_docstring"] is False
        assert obj.test_method.__func__._toolspec_kwargs["description"] == "Custom description"


class TestToolRegistry:
    """Test the ToolRegistry mixin class."""

    def test_basic_registration(self):
        """Test that methods are registered correctly."""

        class TestClass(ToolRegistry):
            @reg_toolspec
            def search(self, query: str) -> str:
                """Search for items.

                Args:
                    query: The search query.

                Returns:
                    str: Search results.
                """
                return f"Results for: {query}"

        obj = TestClass()
        tools = obj.to_toolspecs()

        assert len(tools) == 1
        assert isinstance(tools["search"], ToolSpec)
        assert tools["search"].binded.name == "search"

    def test_multiple_tools(self):
        """Test registration of multiple tools."""

        class TestClass(ToolRegistry):
            @reg_toolspec
            def search(self, query: str) -> str:
                """Search for items."""
                return f"Results for: {query}"

            @reg_toolspec
            def filter(self, items: List[str]) -> List[str]:
                """Filter items."""
                return [i for i in items if len(i) > 0]

        obj = TestClass()
        tools = obj.to_toolspecs()

        assert len(tools) == 2
        assert set(tools.keys()) == {"search", "filter"}

    def test_list_toolspecs(self):
        """Test listing tool names."""

        class TestClass(ToolRegistry):
            @reg_toolspec
            def search(self, query: str) -> str:
                """Search for items."""
                return f"Results for: {query}"

            @reg_toolspec
            def filter(self, items: List[str]) -> List[str]:
                """Filter items."""
                return items

        obj = TestClass()
        tool_names = obj.list_toolspecs()

        assert len(tool_names) == 2
        assert "search" in tool_names
        assert "filter" in tool_names

    def test_tool_execution(self):
        """Test that tools can be executed."""

        class TestClass(ToolRegistry):
            def __init__(self):
                super().__init__()
                self.data = ["apple", "banana", "cherry"]

            @reg_toolspec(parse_docstring=True)
            def search(self, query: str) -> str:
                """Search for items.

                Args:
                    query: The search query.

                Returns:
                    str: Search results.
                """
                results = [item for item in self.data if query.lower() in item.lower()]
                return ", ".join(results)

        obj = TestClass()
        tools = obj.to_toolspecs()

        assert len(tools) == 1
        tool = tools["search"]

        # Execute the tool
        result = tool.call(query="an")
        assert "banana" in result

    def test_self_binding(self):
        """Test that self is properly bound to tools."""

        class TestClass(ToolRegistry):
            def __init__(self, value: int):
                super().__init__()
                self.value = value

            @reg_toolspec
            def get_value(self) -> int:
                """Get the instance value.

                Returns:
                    int: The instance value.
                """
                return self.value

        obj1 = TestClass(42)
        obj2 = TestClass(99)

        tools1 = obj1.to_toolspecs()
        tools2 = obj2.to_toolspecs()

        assert tools1["get_value"].call() == 42
        assert tools2["get_value"].call() == 99

    def test_docstring_parsing(self):
        """Test that docstrings are parsed correctly."""

        class TestClass(ToolRegistry):
            @reg_toolspec(parse_docstring=True)
            def search(self, query: str) -> str:
                """Search for items with the given query.

                Args:
                    query: The search query string to use.

                Returns:
                    str: The search results as a string.
                """
                return f"Results for: {query}"

        obj = TestClass()
        tools = obj.to_toolspecs()
        tool = tools["search"]

        assert "search" in tool.binded.description.lower()
        assert "query" in tool.input_schema["properties"]
        assert "query" in str(tool.docstring).lower()


class TestKLBaseIntegration:
    """Test ToolRegistry integration with KLBase."""

    def test_klbase_custom_search(self):
        """Test adding custom search methods to KLBase."""

        class MyCustomKLBase(KLBase):
            @reg_toolspec(parse_docstring=True)
            def custom_search(self, query: str) -> str:
                """Custom search implementation.

                Args:
                    query: The search query.

                Returns:
                    str: Search results.
                """
                return f"Custom search: {query}"

        kb = MyCustomKLBase()
        tools = kb.to_toolspecs()

        assert len(tools) >= 1
        assert "custom_search" in set(tools.keys())

        # Find and execute the custom search tool
        custom_tool = tools["custom_search"]
        result = custom_tool.call(query="test")
        assert result == "Custom search: test"

    def test_klbase_with_storages_and_engines(self):
        """Test that custom tools work with existing KLBase functionality."""

        class MyKLBase(KLBase):
            @reg_toolspec
            def count_storages(self) -> int:
                """Count the number of storages.

                Returns:
                    int: Number of storages.
                """
                return len(self.storages)

            @reg_toolspec
            def count_engines(self) -> int:
                """Count the number of engines.

                Returns:
                    int: Number of engines.
                """
                return len(self.engines)

        kb = MyKLBase()
        tools = kb.to_toolspecs()

        assert len(tools) == 2

        count_storages_tool = tools["count_storages"]
        count_engines_tool = tools["count_engines"]

        assert count_storages_tool.call() == 0
        assert count_engines_tool.call() == 0


class TestKLEngineIntegration:
    """Test ToolRegistry integration with BaseKLEngine."""

    def test_klengine_custom_method(self):
        """Test adding custom methods to KLEngine."""

        class MyKLEngine(BaseKLEngine):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.search_count = 0

            @reg_toolspec(parse_docstring=True)
            def get_search_count(self) -> int:
                """Get the number of searches performed.

                Returns:
                    int: Number of searches.
                """
                return self.search_count

            def _search(self, *args, **kwargs):
                self.search_count += 1
                return []

            def _upsert(self, kl):
                pass

            def _remove(self, key):
                pass

            def _clear(self):
                pass

        engine = MyKLEngine()
        tools = engine.to_toolspecs()

        assert len(tools) >= 1
        assert "get_search_count" in set(tools.keys())

        # Execute search to increment counter
        engine.search()
        engine.search()

        # Get the tool and execute it
        count_tool = tools["get_search_count"]
        assert count_tool.call() == 2


class TestKLStoreIntegration:
    """Test ToolRegistry integration with BaseKLStore."""

    def test_klstore_custom_method(self):
        """Test adding custom methods to KLStore."""

        class MyKLStore(BaseKLStore):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.items = {}

            @reg_toolspec(parse_docstring=True)
            def get_count(self) -> int:
                """Get the number of items in the store.

                Returns:
                    int: Number of items.
                """
                return len(self.items)

            def _get(self, key, default=...):
                return self.items.get(key, default)

            def _upsert(self, kl):
                self.items[kl.id] = kl

            def _remove(self, key):
                self.items.pop(key, None)

            def _itervalues(self):
                return iter(self.items.values())

            def _clear(self):
                self.items.clear()

        store = MyKLStore()
        tools = store.to_toolspecs()

        assert len(tools) >= 1
        assert "get_count" in set(tools.keys())

        # Get the tool and execute it
        count_tool = tools["get_count"]
        assert count_tool.call() == 0


class TestToolToJsonSchema:
    """Test conversion of tools to JSON schema format."""

    def test_tool_to_jsonschema(self):
        """Test that tools can be converted to JSON schema for LLM use."""

        class TestClass(ToolRegistry):
            @reg_toolspec(parse_docstring=True)
            def search(self, query: str, limit: int = 10) -> str:
                """Search for items.

                Args:
                    query: The search query.
                    limit: Maximum number of results.

                Returns:
                    str: Search results.
                """
                return f"Results for: {query} (limit: {limit})"

        obj = TestClass()
        tools = obj.to_toolspecs()
        tool = tools["search"]

        schema = tool.to_jsonschema()

        assert schema["type"] == "function"
        assert schema["name"] == "search"
        assert "query" in schema["parameters"]["properties"]
        assert "limit" in schema["parameters"]["properties"]
        assert schema["strict"] is True
