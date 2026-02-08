from langchain_core.messages import HumanMessage

from .graph import build_graph


def main() -> None:
    graph = build_graph()
    result = graph.invoke(
        {
            "messages": [
                HumanMessage(
                    content="What time is it in UTC and what is 19 + 23?"
                )
            ]
        }
    )
    final_message = result["messages"][-1]
    print(final_message.content)


if __name__ == "__main__":
    main()
