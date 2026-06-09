from typing import Optional, Any

from langgraph.graph.state import CompiledStateGraph
from typing_extensions import TypedDict, Annotated

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages


from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

from langsmith import traceable

from app.config import get_settings


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    error: Optional[str]
    retry_count: int
    model: str


class Agent:
    def __init__(self):
        self.settings = get_settings()
        self.primary_llm = ChatGoogleGenerativeAI(
            model=self.settings.PRIMARY_MODEL,
            temperature=self.settings.MODEL_TEMPERATURE,
            timeout=30,
            max_retries=self.settings.MAX_RETRIES,
        )
        self.fallback_llm = ChatGoogleGenerativeAI(
            model=self.settings.FALLBACK_MODEL,
            temperature=self.settings.MODEL_TEMPERATURE,
            timeout=30,
            max_retries=self.settings.MAX_RETRIES,
        )
        self.graph = self._build_graph()

    def _build_graph(self) -> CompiledStateGraph:

        def process_message(state: AgentState) -> dict[str, Optional[Any]]:

            try:
                response = self.primary_llm.invoke(state["messages"])

                return {
                    "messages": response,
                    "error": None,
                    "retry_count": state["retry_count"],
                    "model": self.primary_llm.model,
                }
            except Exception as e:
                return {
                    "error": str(e),
                    "retry_count": state["retry_count"] + 1,
                    "model": self.fallback_llm.model,
                }

        def try_fallback(state: AgentState) -> dict[str, Optional[Any]]:
            try:
                response = self.fallback_llm.invoke(state["messages"])
                return {
                    "messages": response,
                    "error": None,
                    "retry_count": state["retry_count"],
                    "model": self.fallback_llm.model,
                }
            except Exception as e:
                return {
                    "error": str(e),
                    "retry_count": state["retry_count"],
                    "model": self.fallback_llm.model,
                }

        def handle_error(state: AgentState) -> dict[str, Optional[Any]]:
            return {
                "messages": [
                    AIMessage(
                        content=(
                            "I am sorry, but I am currently experiencing technical difficulties and cannot process your request. Please try again later."
                        )
                    )
                ],
                "model": "error_handler",
            }

        def route_after_primary(state: AgentState) -> str:
            if state["error"] is None:
                return "done"
            elif state["retry_count"] < self.settings.MAX_RETRIES:
                return "try_fallback"
            else:
                return "error"

        def route_after_fallback(state: AgentState) -> str:
            if state["error"] is None:
                return "done"
            else:
                return "error"

        graph = StateGraph(AgentState)

        graph.add_node("process", process_message)
        graph.add_node("try_fallback", try_fallback)
        graph.add_node("error", handle_error)

        graph.add_edge(START, "process")
        graph.add_conditional_edges(
            "process", route_after_primary, {"done": END, "try_fallback": "try_fallback", "error": "error"}
        )
        graph.add_conditional_edges("try_fallback", route_after_fallback, {"done": END, "error": "error"})
        graph.add_edge("error", END)

        return graph.compile()

    @traceable(name="agent_run")
    def invoke(self, query: str):
        response = self.graph.invoke(
            {
                "messages": [HumanMessage(content=query)],
                "error": None,
                "retry_count": 0,
                "model": None,
            }
        )
        return {
            "response": response["messages"][-1].content if response.get("messages") else None,
            "model_used": response.get("model", "unknown"),
            "error": response.get("error"),
        }
