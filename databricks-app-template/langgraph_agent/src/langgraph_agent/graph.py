from __future__ import annotations

from typing import Annotated, Sequence, TypedDict

from databricks_langchain import ChatDatabricks
from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from .config import load_config
from .tools import TOOL_LIST


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]


SYSTEM_PROMPT = (
    "You are an expert data analyst assistant. Use tools when they add value or improve accuracy.\n"
    "Present results clearly, precisely, and in a way that best supports decision-making, adapting "
    "the format to the type, scale, and complexity of the data:\n"
    "• Tabular data:\n"
    "  • Always return results as markdown tables\n"
    "  • Use clear column names, appropriate ordering, and consistent units\n"
    "  • Aggregate, sort, or filter where it improves readability\n"
    "• Comparisons & analysis:\n"
    "  • Structure outputs logically (e.g., grouped sections, stepwise comparisons)\n"
    "  • Use tables for quantitative comparisons and concise bullets for key takeaways\n"
    "  • Highlight trends, outliers, and meaningful differences\n"
    "• Complex or multi-dimensional data:\n"
    "  • Break down results into interpretable sections\n"
    "  • Summarize insights before or after detailed tables\n"
    "  • Avoid unnecessary verbosity while preserving analytical rigor\n"
    "• General principles:\n"
    "  • Prefer clarity over completeness\n"
    "  • Explicitly state assumptions when needed\n"
    "  • Use consistent formatting and terminology throughout"
)


def build_graph(system_prompt: str | None = None):
    config = load_config()
    if not config.model_endpoint:
        raise ValueError("DATABRICKS_MODEL_ENDPOINT is required to build the graph.")

    llm = ChatDatabricks(endpoint=config.model_endpoint, temperature=0)
    llm_with_tools = llm.bind_tools(TOOL_LIST)
    tool_node = ToolNode(TOOL_LIST)

    resolved_prompt = system_prompt or SYSTEM_PROMPT

    def call_model(state: AgentState):
        messages = list(state["messages"])
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=resolved_prompt), *messages]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def route_from_agent(state: AgentState):
        last_message = state["messages"][-1]
        if getattr(last_message, "tool_calls", None):
            return "tools"
        return "end"

    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", tool_node)
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges(
        "agent",
        route_from_agent,
        {
            "tools": "tools",
            "end": END,
        },
    )
    workflow.add_edge("tools", "agent")
    return workflow.compile()
