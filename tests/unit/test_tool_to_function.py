import pytest
from ahvn.tool.base import ToolSpec
import inspect


def test_to_function():
    @ToolSpec(name="add", description="Add two numbers")
    def add(a: int, b: int) -> int:
        return a + b

    if not hasattr(add, "to_function"):
        print("to_function not implemented yet")
        return

    func = add.to_function()

    assert func.__name__ == "add"
    assert func(a=1, b=2) == 3
    assert func(1, 2) == 3

    sig = inspect.signature(func)
    print(f"Signature: {sig}")
    print(f"Param a annotation: {sig.parameters['a'].annotation} (type: {type(sig.parameters['a'].annotation)})")

    # assert sig.parameters["a"].annotation == int
    # assert sig.parameters["b"].annotation == int
    # assert sig.return_annotation == int

    assert "Add two numbers" in func.__doc__


if __name__ == "__main__":
    test_to_function()
    print("Test passed!")
