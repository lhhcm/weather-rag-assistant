from __future__ import annotations

from typing import Any, Literal, TypedDict

from .assistant import (
    build_retrieval_query,
    classify_intent,
    compose_answer,
    detect_period,
    should_fetch_weather,
    trim_text,
)
from .rag import LocalVectorStore, SearchResult
from .weather_api import WeatherApiError, assess_risks, detect_location, fetch_weather


class WeatherRagState(TypedDict, total=False):
    question: str
    cleaned_question: str
    error: str
    location: str
    intent: str
    period: str
    fetch_required: bool
    weather: dict[str, Any] | None
    weather_error: str
    risks: list[dict[str, str]]
    retrieval_query: str
    results: list[SearchResult]
    answer: str
    graph_trace: list[str]


class GraphWeatherRagAssistant:
    """LangGraph orchestration for the weather RAG workflow.

    LangGraph is optional at runtime so the demo can still run before
    dependencies are installed. When available, ask() executes the compiled
    state graph; otherwise it follows the same nodes in linear order.
    """

    graph_nodes = [
        "validate_question",
        "understand_question",
        "fetch_weather",
        "retrieve_knowledge",
        "generate_answer",
    ]
    graph_edges = [
        ("validate_question", "understand_question"),
        ("understand_question", "fetch_weather / retrieve_knowledge"),
        ("fetch_weather", "retrieve_knowledge"),
        ("retrieve_knowledge", "generate_answer"),
    ]

    def __init__(self, vector_store: LocalVectorStore | None = None) -> None:
        self.vector_store = vector_store or LocalVectorStore.from_directory()
        self.graph_app = self._build_langgraph_app()

    @property
    def graph_enabled(self) -> bool:
        return self.graph_app is not None

    def ask(self, question: str) -> dict[str, Any]:
        initial_state: WeatherRagState = {"question": question, "graph_trace": []}
        if self.graph_app is not None:
            final_state = self.graph_app.invoke(initial_state)
        else:
            final_state = self._invoke_fallback(initial_state)
        return self._to_response(final_state)

    def validate_question(self, state: WeatherRagState) -> WeatherRagState:
        question = state.get("question", "")
        cleaned_question = question.strip()
        trace = [*state.get("graph_trace", []), "validate_question"]
        if not cleaned_question:
            return {**state, "cleaned_question": "", "error": "问题不能为空", "graph_trace": trace}
        return {**state, "cleaned_question": cleaned_question, "graph_trace": trace}

    def understand_question(self, state: WeatherRagState) -> WeatherRagState:
        question = state.get("cleaned_question", "")
        trace = [*state.get("graph_trace", []), "understand_question"]
        fetch_required = should_fetch_weather(question)
        return {
            **state,
            "location": detect_location(question) if fetch_required else "",
            "intent": classify_intent(question),
            "period": detect_period(question),
            "fetch_required": fetch_required,
            "graph_trace": trace,
        }

    def fetch_weather_node(self, state: WeatherRagState) -> WeatherRagState:
        trace = [*state.get("graph_trace", []), "fetch_weather"]
        try:
            weather = fetch_weather(state.get("location", "上海"))
            risks = assess_risks(weather, state.get("period", "today"))
            return {**state, "weather": weather, "weather_error": "", "risks": risks, "graph_trace": trace}
        except WeatherApiError as exc:
            return {**state, "weather": None, "weather_error": str(exc), "risks": [], "graph_trace": trace}

    def retrieve_knowledge(self, state: WeatherRagState) -> WeatherRagState:
        trace = [*state.get("graph_trace", []), "retrieve_knowledge"]
        query = build_retrieval_query(
            state.get("cleaned_question", ""),
            state.get("intent", "综合"),
            state.get("period", "today"),
            state.get("weather"),
            state.get("risks", []),
        )
        results = self.vector_store.search(query, top_k=4)
        return {**state, "retrieval_query": query, "results": results, "graph_trace": trace}

    def generate_answer(self, state: WeatherRagState) -> WeatherRagState:
        trace = [*state.get("graph_trace", []), "generate_answer"]
        if state.get("error"):
            return {**state, "answer": state["error"], "graph_trace": trace}

        answer = compose_answer(
            state.get("cleaned_question", ""),
            state.get("location", ""),
            state.get("intent", "综合"),
            state.get("period", "today"),
            state.get("weather"),
            state.get("weather_error", ""),
            state.get("risks", []),
            state.get("results", []),
        )
        return {**state, "answer": answer, "graph_trace": trace}

    def route_after_understanding(self, state: WeatherRagState) -> Literal["fetch_weather", "retrieve_knowledge"]:
        return "fetch_weather" if state.get("fetch_required") else "retrieve_knowledge"

    def _build_langgraph_app(self):
        try:
            from langgraph.graph import END, StateGraph
        except ImportError:
            return None

        graph = StateGraph(WeatherRagState)
        graph.add_node("validate_question", self.validate_question)
        graph.add_node("understand_question", self.understand_question)
        graph.add_node("fetch_weather", self.fetch_weather_node)
        graph.add_node("retrieve_knowledge", self.retrieve_knowledge)
        graph.add_node("generate_answer", self.generate_answer)

        graph.set_entry_point("validate_question")
        graph.add_edge("validate_question", "understand_question")
        graph.add_conditional_edges(
            "understand_question",
            self.route_after_understanding,
            {
                "fetch_weather": "fetch_weather",
                "retrieve_knowledge": "retrieve_knowledge",
            },
        )
        graph.add_edge("fetch_weather", "retrieve_knowledge")
        graph.add_edge("retrieve_knowledge", "generate_answer")
        graph.add_edge("generate_answer", END)
        return graph.compile()

    def _invoke_fallback(self, state: WeatherRagState) -> WeatherRagState:
        state = self.validate_question(state)
        if state.get("error"):
            return self.generate_answer(state)
        state = self.understand_question(state)
        if state.get("fetch_required"):
            state = self.fetch_weather_node(state)
        state = self.retrieve_knowledge(state)
        return self.generate_answer(state)

    def _to_response(self, state: WeatherRagState) -> dict[str, Any]:
        if state.get("error"):
            return {"error": state["error"], "graph_trace": state.get("graph_trace", [])}

        results = state.get("results", [])
        return {
            "answer": state.get("answer", ""),
            "location": state.get("location") or "知识问答",
            "intent": state.get("intent", "综合"),
            "period": state.get("period", "today"),
            "weather": state.get("weather"),
            "weather_error": state.get("weather_error", ""),
            "risks": state.get("risks", []),
            "graph": {
                "enabled": self.graph_enabled,
                "backend": "langgraph" if self.graph_enabled else "linear-fallback",
                "trace": state.get("graph_trace", []),
                "nodes": self.graph_nodes,
                "edges": self.graph_edges,
            },
            "sources": [
                {
                    "id": result.chunk.id,
                    "title": result.chunk.title,
                    "source": result.chunk.source,
                    "score": round(result.score, 4),
                    "snippet": trim_text(result.chunk.text, 180),
                }
                for result in results
            ],
        }
