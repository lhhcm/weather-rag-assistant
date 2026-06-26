from pathlib import Path

from src.weather_rag.graph_assistant import GraphWeatherRagAssistant
from src.weather_rag.rag import LocalVectorStore


ROOT = Path(__file__).resolve().parents[1]


def test_graph_fallback_or_langgraph_response_shape() -> None:
    store = LocalVectorStore.from_directory(ROOT / "data" / "weather_docs")
    assistant = GraphWeatherRagAssistant(store)
    response = assistant.ask("为什么湿度高会觉得闷热？")

    assert response["intent"] == "科普"
    assert response["graph"]["trace"] == [
        "validate_question",
        "understand_question",
        "retrieve_knowledge",
        "generate_answer",
    ]
    assert response["answer_backend"] in {"langchain-local-rag", "langchain-llm"}
    assert "connected" in response["llm"]
    assert response["sources"]


def test_concept_question_does_not_default_to_shanghai() -> None:
    store = LocalVectorStore.from_directory(ROOT / "data" / "weather_docs")
    assistant = GraphWeatherRagAssistant(store)
    response = assistant.ask("厄尔尼诺是什么？")

    assert response["location"] == "知识问答"
    assert response["weather"] is None
    assert "fetch_weather" not in response["graph"]["trace"]
    assert any("厄尔尼诺" in source["title"] for source in response["sources"])
