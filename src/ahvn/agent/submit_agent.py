__all__ = [
    "SubmitToolAgentSpec",
]

from .base import BasePromptAgentSpec
from ..llm.base import Messages
from ..utils.basic.serialize_utils import loads_json
from ..ukf.templates.basic.prompt import PromptUKFT
from ..tool.base import ToolSpec
from typing import Dict, Any, List, Optional, Tuple


class SubmitToolAgentSpec(BasePromptAgentSpec):
    """
    Agent that runs until a 'submit' tool call is encountered.
    The return value of the submit tool call is used as the final output.
    """

    def __init__(
        self,
        prompt: PromptUKFT,
        tools: Optional[List[ToolSpec]] = None,
        llm_args: Optional[Dict] = None,
        max_steps: Optional[int] = None,
        submit_name: str = "submit",
        error_signal: str = "[ERROR]",
        tool_instructions: bool = True,
        **kwargs,
    ):
        if tool_instructions:
            prompt.bind(
                instructions=prompt.get("binds.instructions", list())
                + [
                    "You may use tools to help complete the task.",
                    "Make sure you use the submit tool to return your final answer. The task is not complete until a successful submit tool call is made. The submit tool:",
                    f"`{submit_name}`",
                ]
            )
            prompt.bind(submit_name=submit_name)
        super().__init__(prompt=prompt, tools=tools, llm_args=llm_args, max_steps=max_steps, **kwargs)

        self.submit_name = submit_name
        # tool_names = [tool.name for tool in self.tools]
        # if tool_names.count(self.submit_name) != 1:
        #     raise ValueError(f"Tools must include a single '{self.submit_name}' tool. Provided tools: {tool_names}")
        self.error_signal = error_signal

    def is_done(self, messages: Messages, delta_messages: List[Dict[str, Any]]) -> Tuple[bool, Dict[str, Any]]:
        if len(delta_messages) == 0:
            return False, None
        for message in reversed(delta_messages):
            if (message.get("role") == "tool") and (message.get("name") == self.submit_name) and (self.error_signal not in message.get("content", "")):
                for call_message in reversed(delta_messages):
                    if (call_message.get("role") == "assistant") and (call_message.get("tool_calls")):
                        for tc in call_message.get("tool_calls", []):
                            if tc.get("id") == message.get("tool_call_id"):
                                return True, {
                                    "msg": "success",
                                    "output": message.get("content"),
                                    "tool_call": tc,
                                    "name": message.get("name"),
                                    "arguments": loads_json(tc.get("function", dict()).get("arguments", "{}")),
                                }
        return False, None

    def decode(self, messages: Messages, finish_state: Dict[str, Any] = None) -> Any:
        if len(messages) == 0:
            return None
        if (finish_state is not None) and (finish_state.get("msg") == "success"):
            return finish_state.get("output")
        return None
