from __future__ import annotations

from typing import Annotated, Sequence, TypedDict

from langchain_core.messages import AIMessage, BaseMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from .config import VectorSearchConfig
from .tools import build_hybrid_retriever_tool


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]


def build_graph(config: VectorSearchConfig):
    tool = build_hybrid_retriever_tool(config)
    tool_node = ToolNode([tool])

    graph = StateGraph(AgentState)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "tools")
    graph.add_edge("tools", END)
    return graph.compile()


def run_hybrid_search(app, query: str, filters: str | None = None, num_results: int | None = None):
    args: dict[str, object] = {"query": query}
    if filters is not None:
        args["filters"] = filters
    if num_results is not None:
        args["num_results"] = num_results

    tool_call = {
        "name": "hybrid_retriever",
        "args": args,
        "id": "hybrid-search-0",
    }
    state = {"messages": [AIMessage(content="", tool_calls=[tool_call])]}
    return app.invoke(state)
