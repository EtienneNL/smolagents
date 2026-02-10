from __future__ import annotations

import asyncio

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import Field

from nat.builder.builder import Builder
from nat.builder.framework_enum import LLMFrameworkEnum
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

from .graph import SYSTEM_PROMPT, build_graph
from .tools import match_column_names, match_nutrient_names, query_nutrient_data


_ROLE_TO_MESSAGE = {
    "user": HumanMessage,
    "assistant": AIMessage,
    "system": SystemMessage,
}


def _coerce_messages(raw_messages) -> list[BaseMessage]:
    messages: list[BaseMessage] = []
    for item in raw_messages or []:
        if isinstance(item, BaseMessage):
            messages.append(item)
            continue
        if isinstance(item, dict):
            role = (item.get("role") or "user").lower()
            content = item.get("content", "")
            message_cls = _ROLE_TO_MESSAGE.get(role, HumanMessage)
            messages.append(message_cls(content=content))
            continue
        messages.append(HumanMessage(content=str(item)))
    return messages


class LangGraphAgentConfig(FunctionBaseConfig, name="langgraph_agent"):
    system_prompt: str | None = Field(
        default=None,
        description="Optional override for the LangGraph system prompt.",
    )


@register_function(
    config_type=LangGraphAgentConfig,
    framework_wrappers=[LLMFrameworkEnum.LANGCHAIN],
)
async def langgraph_agent_function(
    config: LangGraphAgentConfig, builder: Builder
):
    graph = build_graph(system_prompt=config.system_prompt or SYSTEM_PROMPT)

    async def _invoke(
        query: str | None = None, messages: list[dict] | None = None
    ) -> str:
        if messages:
            state_messages = _coerce_messages(messages)
        elif query:
            state_messages = [HumanMessage(content=query)]
        else:
            raise ValueError("Provide either 'query' or 'messages' to langgraph_agent.")

        if hasattr(graph, "ainvoke"):
            result = await graph.ainvoke({"messages": state_messages})
        else:
            result = await asyncio.to_thread(
                graph.invoke, {"messages": state_messages}
            )
        result_messages = result.get("messages") if isinstance(result, dict) else None
        if not result_messages:
            return ""
        last_message = result_messages[-1]
        return last_message.content if hasattr(last_message, "content") else str(last_message)

    yield FunctionInfo.from_fn(
        _invoke,
        description=(
            "Invoke the LangGraph workflow using a Databricks-backed LLM "
            "and data tools."
        ),
    )


class MatchNutrientNamesConfig(FunctionBaseConfig, name="match_nutrient_names"):
    """Expose match_nutrient_names as a NAT tool."""


@register_function(config_type=MatchNutrientNamesConfig)
async def match_nutrient_names_function(
    config: MatchNutrientNamesConfig, builder: Builder
):
    yield match_nutrient_names


class MatchColumnNamesConfig(FunctionBaseConfig, name="match_column_names"):
    """Expose match_column_names as a NAT tool."""


@register_function(config_type=MatchColumnNamesConfig)
async def match_column_names_function(
    config: MatchColumnNamesConfig, builder: Builder
):
    yield match_column_names


class QueryNutrientDataConfig(FunctionBaseConfig, name="query_nutrient_data"):
    """Expose query_nutrient_data as a NAT tool."""


@register_function(config_type=QueryNutrientDataConfig)
async def query_nutrient_data_function(
    config: QueryNutrientDataConfig, builder: Builder
):
    yield query_nutrient_data
