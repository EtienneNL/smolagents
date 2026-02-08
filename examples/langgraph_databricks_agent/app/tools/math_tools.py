from langchain_core.tools import tool


@tool
def add(a: float, b: float) -> float:
    """Return the sum of two numbers."""
    return a + b
