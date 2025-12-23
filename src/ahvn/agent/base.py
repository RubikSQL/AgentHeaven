__all__ = [
    "BaseAgentSpec",
    "BasePromptAgentSpec",
    "AgentStreamChunk",
]

from ..utils.basic.misc_utils import unique
from ..utils.basic.config_utils import HEAVEN_CM
from ..utils.basic.serialize_utils import dumps_json
from ..utils.basic.log_utils import get_logger

logger = get_logger(__name__)

from ..llm import Messages, LLM, LLMIncludeType, gather_stream, format_messages
from ..ukf.templates.basic.prompt import PromptUKFT
from ..tool.base import ToolSpec
from typing import Dict, Any, List, Optional, Generator, Tuple, Union

from abc import ABC, abstractmethod
from copy import deepcopy


# Type alias for stream chunks
AgentStreamChunk = Dict[str, Any]


class BaseAgentSpec(ABC):
    def __init__(
        self,
        tools: Optional[List[ToolSpec]] = None,
        llm_args: Optional[Dict] = None,
        max_steps: Optional[int] = None,
        **kwargs,
    ):
        super().__init__()
        self.tools = tools or list()
        self.llm = LLM(**(llm_args or dict()))
        self.max_steps = HEAVEN_CM.get("agent.max_steps", 20) if max_steps is None else max_steps

    @abstractmethod
    def encode(self, **inputs) -> Messages:
        """\
        Convert input arguments into Messages for the agent.

        Args:
            **inputs: Arbitrary input arguments.

        Returns:
            Messages: The encoded messages for the agent.
        """
        pass

    def step(self, messages: Messages, include: Optional[List[LLMIncludeType]] = None) -> Generator[AgentStreamChunk, None, None]:
        """\
        Execute a single LLM call with streaming.

        Args:
            messages: Current conversation messages.
            include: Fields to include in the stream chunks.

        Yields:
            Stream chunks from the LLM.
        """
        for chunk in self.llm.stream(messages, tools=self.tools, include=include, reduce=False):
            yield chunk

    @abstractmethod
    def is_done(self, messages: Messages, delta_messages: List[Dict[str, Any]]) -> Tuple[bool, Dict[str, Any]]:
        pass

    def user_proxy(self, messages: Messages, delta_messages: List[Dict[str, Any]], finish_state: Dict[str, Any] = None) -> Messages:
        """\
        Add a user proxy message to prompt the agent to continue.

        This is called when the agent is not done after a step, to
        encourage it to keep going.

        Args:
            messages: Current conversation messages.
            delta_messages: Delta messages from the last step.
            finish_state: Optional finish state from the last step.

        Returns:
            Messages: A list of messages to append.
        """
        return [{"role": "user", "content": "The task is not complete. Please continue until the task is complete."}]

    @abstractmethod
    def decode(self, messages: Messages, finish_state: Dict[str, Any] = None) -> Any:
        pass

    def stream(self, messages: Messages, include: Optional[List[LLMIncludeType]] = None) -> Generator[AgentStreamChunk, None, None]:
        """\
        Stream the agent execution, yielding chunks as they are generated.

        This is the core streaming interface. Each chunk contains:
        - Standard LLM fields: text, think, tool_calls, tool_messages, etc.
        - Agent control fields: step, done, finish_state, messages

        Args:
            messages: Initial messages to start the agent.
            include: Fields to include in the stream. Defaults to common fields.

        Yields:
            AgentStreamChunk: Stream chunks with LLM output and agent state.
        """
        default_include = ["text", "think", "tool_calls", "tool_messages", "delta_messages"]
        include = unique((include or default_include) + ["delta_messages"])
        cloned_messages = deepcopy(messages)

        for step_num in range(self.max_steps):
            # Emit step start
            yield {"step": step_num, "step_status": "start"}

            delta_messages = list()

            # Stream the LLM step
            for chunk in self.step(cloned_messages, include=include):
                # Pass through LLM chunks
                yield chunk
                # Collect delta_messages
                if chunk.get("delta_messages"):
                    delta_messages.extend(chunk.get("delta_messages", list()))

            # Update messages
            cloned_messages.extend(delta_messages)

            # Check for stale (no output)
            if len(delta_messages) == 0:
                finish_state = {"msg": "stale", "steps": step_num + 1, "max_steps": self.max_steps}
                yield {"step": step_num, "step_status": "end", "done": True, "finish_state": finish_state, "messages": cloned_messages}
                return

            # Check if done
            done, finish_state = self.is_done(messages=cloned_messages, delta_messages=delta_messages)
            if done:
                finish_state = (finish_state or {}) | {"steps": step_num + 1, "max_steps": self.max_steps}
                yield {"step": step_num, "step_status": "end", "done": True, "finish_state": finish_state, "messages": cloned_messages}
                return

            # Add user proxy message if needed for continuation
            user_proxy_messages = []
            if cloned_messages and cloned_messages[-1].get("role") == "assistant":
                user_proxy_messages = self.user_proxy(cloned_messages, delta_messages, finish_state=finish_state)
                delta_messages.extend(user_proxy_messages)
                cloned_messages.extend(user_proxy_messages)

            # Emit step end (not done yet), include user_proxy messages for session storage
            yield {"step": step_num, "step_status": "end", "done": False, "delta_messages": user_proxy_messages}

        # Max steps reached
        finish_state = {"msg": "max_steps_reached", "steps": self.max_steps, "max_steps": self.max_steps}
        yield {"step": self.max_steps - 1, "step_status": "end", "done": True, "finish_state": finish_state, "messages": cloned_messages}

    def run(self, messages: Messages, include: Optional[List[LLMIncludeType]] = None) -> Tuple[Messages, Dict[str, Any]]:
        """\
        Run the agent to completion, collecting all stream output.

        This is a convenience wrapper around stream() that blocks until completion.

        Args:
            messages: Initial messages to start the agent.
            include: Fields to include (passed to stream).

        Returns:
            Tuple of (final_messages, finish_state).
        """
        final_messages = messages
        finish_state = {"msg": "unknown"}

        for chunk in self.stream(messages, include=include):
            if chunk.get("done"):
                finish_state = chunk.get("finish_state", finish_state)
                final_messages = chunk.get("messages", final_messages)

        return final_messages, finish_state

    def __call__(self, **inputs) -> Any:
        """\
        Convenience method to encode, run, and decode in one call.

        Args:
            **inputs: Input arguments passed to encode().

        Returns:
            Decoded output from the agent.
        """
        encoded_messages = self.encode(**inputs)
        final_messages, finish_state = self.run(encoded_messages)
        decoded_output = self.decode(final_messages, finish_state=finish_state)
        return decoded_output


class BasePromptAgentSpec(BaseAgentSpec):
    def __init__(
        self,
        prompt: PromptUKFT,
        tools: Optional[List[ToolSpec]] = None,
        llm_args: Optional[Dict] = None,
        max_steps: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(tools=tools, llm_args=llm_args, max_steps=max_steps, **kwargs)
        self.prompt = prompt.clone()

    def encode(self, **inputs) -> Messages:
        return format_messages(self.prompt.text(instance={"inputs": inputs}))
