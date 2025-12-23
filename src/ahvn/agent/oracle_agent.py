__all__ = [
    "OracleAgentSpec",
]

from ..llm import Messages
from ..ukf.templates.basic.prompt import PromptUKFT
from typing import Dict, Any, List, Optional, Tuple


from .base import BasePromptAgentSpec


class OracleAgentSpec(BasePromptAgentSpec):
    def __init__(
        self,
        prompt: PromptUKFT,
        llm_args: Optional[Dict] = None,
        **kwargs,
    ):
        super().__init__(prompt=prompt, tools=list(), llm_args=llm_args, max_steps=1, **kwargs)

    def is_done(self, messages: Messages, delta_messages: List[Dict[str, Any]]) -> Tuple[bool, Dict[str, Any]]:
        return True, {"msg": "oracle"}

    def decode(self, messages: Messages, finish_state: Dict[str, Any] = None) -> Any:
        if len(messages) == 0:
            return None
        return messages[-1].get("content", None)
