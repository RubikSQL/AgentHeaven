import json
import pytest

from ahvn.llm.base import exec_tool_calls
from ahvn.tool.base import ToolSpec


def echo(value: int = 0) -> int:
    return value


def failer() -> None:
    raise ValueError("boom")


def no_args() -> str:
    return "ok"


def _spec_map(spec: ToolSpec) -> dict:
    return {spec.binded.name: spec}


class TestExecToolCalls:
    def test_exec_tool_calls_basic(self):
        spec = ToolSpec.from_function(echo)
        tool_calls = [
            {
                "id": "abc",
                "function": {"name": spec.binded.name, "arguments": json.dumps({"value": 5})},
            }
        ]

        tool_messages, tool_results = exec_tool_calls(tool_calls, _spec_map(spec))

        assert tool_results == ["5"]
        assert tool_messages == [
            {
                "role": "tool",
                "tool_call_id": "abc",
                "name": spec.binded.name,
                "content": "5",
            }
        ]

    def test_exec_tool_calls_without_function_layer(self):
        spec = ToolSpec.from_function(echo)
        tool_calls = [
            {
                "name": spec.binded.name,
                "arguments": {"value": 7},
            }
        ]

        tool_messages, tool_results = exec_tool_calls(tool_calls, _spec_map(spec))

        assert tool_results == ["7"]
        assert tool_messages[0]["tool_call_id"] == ""
        assert tool_messages[0]["name"] == spec.binded.name

    def test_exec_tool_calls_dict_arguments(self):
        spec = ToolSpec.from_function(no_args)
        tool_calls = [
            {
                "id": "",
                "function": {"name": spec.binded.name, "arguments": {}},
            }
        ]

        tool_messages, tool_results = exec_tool_calls(tool_calls, _spec_map(spec))

        assert tool_results == ["ok"]
        assert tool_messages[0]["content"] == "ok"

    def test_exec_tool_calls_malformed_json(self):
        spec = ToolSpec.from_function(echo)
        tool_calls = [
            {
                "function": {"name": spec.binded.name, "arguments": "{bad"},
            }
        ]

        tool_messages, tool_results = exec_tool_calls(tool_calls, _spec_map(spec))

        assert "Failed to parse arguments" in tool_results[0]
        assert "Failed to parse arguments" in tool_messages[0]["content"]

    def test_exec_tool_calls_execution_error(self):
        spec = ToolSpec.from_function(failer)
        tool_calls = [
            {
                "function": {"name": spec.binded.name, "arguments": "{}"},
            }
        ]

        tool_messages, tool_results = exec_tool_calls(tool_calls, _spec_map(spec))

        assert tool_results[0].startswith(f"Error executing tool '{spec.binded.name}'")

    def test_exec_tool_calls_missing_name(self):
        spec = ToolSpec.from_function(echo)
        tool_calls = [
            {
                "function": {},
            }
        ]

        with pytest.raises(ValueError):
            exec_tool_calls(tool_calls, _spec_map(spec))
