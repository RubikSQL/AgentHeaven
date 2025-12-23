from ahvn.llm import LLM, format_messages, exec_tool_calls
from ahvn.utils.basic.parser_utils import parse_md, parse_fc
from ahvn.ukf.templates.basic.prompt import PromptUKFT
from ahvn.cache import InMemCache
from ahvn.tool import ToolSpec

cache = InMemCache()


@cache.memoize()
def fibonacci(n: int) -> int:
    """\
    Compute the nth Fibonacci number.

    Args:
        n (int): The position in the Fibonacci sequence.

    Returns:
        int: The nth Fibonacci number.
    """
    return n if n <= 1 else fibonacci(n - 2) + fibonacci(n - 1)


def multiply(a: int, b: int) -> int:
    """\
    Multiply two integers.
    Make sure you use this tool for multiplication to prevent computation errors.

    Args:
        a (int): The first integer.
        b (int): The second integer.

    Returns:
        int: The product of the two integers.
    """
    return a * b


def submit(val: int) -> int:
    """\
    Submit a value to be processed.

    Args:
        val (int): The value to process.

    Returns:
        int: The processed value.
    """
    return val


fib_tool = ToolSpec.from_function(fibonacci)
mul_tool = ToolSpec.from_function(multiply)
# submit_tool = ToolSpec.from_function(submit)
toolspec_dict = {
    fib_tool.binded.name: fib_tool,
    mul_tool.binded.name: mul_tool,
    # submit_tool.binded.name: submit_tool,
}

llm = LLM(preset="chat")

messages = format_messages("What is `Fib(32) * Fib(64)` ?")

p = PromptUKFT.from_path("& prompts/system", default_entry="prompt.jinja")
p.bind(system="You are a helpful math assistant, use the tools to answer user queries.")


from ahvn.agent.conv_agent import ConvToolAgentSpec
from ahvn.utils.basic.color_utils import color_grey


agent = ConvToolAgentSpec(prompt=p, tools=[fib_tool, mul_tool], llm_args={"preset": "chat"})

# Streaming demo
query = "What is `Fib(32) * Fib(64)` ?"
print(f"Query: {query}")
print()

encoded = agent.encode(query=query)
finish_state = None
final_messages = None

for chunk in agent.stream(encoded, include=["text", "think", "tool_calls", "tool_messages", "delta_messages"]):
    if "step" in chunk and "step_status" in chunk:
        if chunk["step_status"] == "start":
            print(color_grey(f"\n--- Step {chunk['step'] + 1} ---"))
        if chunk["step_status"] == "end" and chunk.get("done"):
            finish_state = chunk.get("finish_state")
            final_messages = chunk.get("messages")
        continue
    if chunk.get("text"):
        print(chunk["text"], end="", flush=True)
    if chunk.get("tool_calls"):
        for tc in chunk["tool_calls"]:
            print(f"\n  → {tc.get('function', tc).get('name', 'unknown')}(...)")
    if chunk.get("tool_messages"):
        for tm in chunk["tool_messages"]:
            print(f"  ← {tm.get('name', 'unknown')}: {tm.get('content', '')}")

print()
print("Agent's Tool Answer:", agent.decode(final_messages, finish_state=finish_state))
print("Ground Truth Answer:", fibonacci(32) * fibonacci(64))
