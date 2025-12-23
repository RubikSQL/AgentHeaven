__all__ = [
    "ConvToolAgentSpec",
]

from ..utils.basic.misc_utils import unique
from ..ukf.templates.basic.prompt import PromptUKFT
from ..llm import Messages, LLM, LLMIncludeType, gather_stream, exec_tool_calls
from ..utils.basic.parser_utils import parse_fc, parse_md
from ..tool.base import ToolSpec
from typing import Dict, Any, List, Optional, Generator, Tuple


from .base import BasePromptAgentSpec, AgentStreamChunk


class ConvToolAgentSpec(BasePromptAgentSpec):
    """\
    Warning: ConvToolAgentSpec is only used to accomodate LLMs that do not support native function calls.
    Whenever possible, for best performance and stability, it is recommended to use
    `LLM.tooluse`, `LLM.oracle(tools=...)`, `SubmitToolAgentSpec`, or other tool use agents instead.
    """

    def __init__(
        self,
        prompt: PromptUKFT,
        tools: Optional[List[ToolSpec]] = None,
        llm_args: Optional[Dict] = None,
        max_steps: Optional[int] = None,
        **kwargs,
    ):
        self.prompt.bind(toolspecs=tools or list())
        super().__init__(prompt=prompt, tools=tools, llm_args=llm_args, max_steps=max_steps, **kwargs)

    def is_done(self, messages: Messages, delta_messages: List[Dict[str, Any]]) -> Tuple[bool, Dict[str, Any]]:
        for message in reversed(delta_messages):
            if message.get("role") == "assistant":
                try:
                    parsed = parse_md(message["content"])
                    return bool("output" in parsed), {"msg": "success", "output": parsed.get("output")}
                except Exception:
                    pass
                break
        return False, None

    def decode(self, messages: Messages, finish_state: Dict[str, Any] = None) -> Any:
        if len(messages) == 0:
            return None
        if (finish_state is not None) and (finish_state.get("msg") == "success"):
            return finish_state.get("output")
        return None

    def step(self, messages: Messages, include: Optional[List[LLMIncludeType]] = None) -> Generator[AgentStreamChunk, None, None]:
        """\
        Execute a single step with conversational tool calling.

        This step streams LLM output, then parses for tool calls and executes them.
        """
        include = include or []
        list_includes = {"tool_calls", "tool_messages", "tool_results", "delta_messages", "messages"}
        delta_include = unique(list(set(include) - list_includes) + ["text", "message", "messages"])

        response = {k: list() for k in list_includes if k in include}

        # Stream LLM response
        for chunk in self.llm.stream(messages, include=delta_include, reduce=False):
            processed_chunk = chunk | {k: list() for k in list_includes if k in include}
            response = gather_stream([response, processed_chunk], include=delta_include, reduce=False)
            yield {k: v for k, v in chunk.items() if k in include}

        # Parse for tool calls
        parsed = parse_md(response.get("text", ""))
        if "tool" in parsed:
            tool_call = parse_fc(parsed["tool"], tools_args={tool.name: list(tool.params) for tool in self.tools})

            # Emit tool_calls if requested
            if "tool_calls" in include:
                yield {"tool_calls": [tool_call]}

            # Execute and emit results
            _, tool_results = exec_tool_calls([tool_call], {tool.name: tool for tool in self.tools})

            # Emit tool_messages if requested
            tool_messages = [{"role": "user", "content": "\n".join([f"<tool_result>\n{result}\n</tool_result>" for result in tool_results])}]
            if "tool_messages" in include:
                yield {"tool_messages": tool_messages}

            delta_messages = [response.get("message")] + tool_messages
        else:
            delta_messages = [response.get("message")]

        # Emit final delta_messages
        yield {
            k: v
            for k, v in {
                "messages": messages + delta_messages,
                "delta_messages": delta_messages,
            }.items()
            if k in include
        }
