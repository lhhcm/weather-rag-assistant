from pathlib import Path

from src.weather_rag.assistant import classify_intent, detect_period, is_weather_domain_question, should_fetch_weather
from src.weather_rag.rag import LocalVectorStore, load_documents


ROOT = Path(__file__).resolve().parents[1]


def test_load_documents() -> None:
    chunks = load_documents(ROOT / "data" / "weather_docs")
    assert len(chunks) >= 6
    assert any("体感温度" in chunk.title for chunk in chunks)


def test_search_returns_relevant_chunk() -> None:
    store = LocalVectorStore.from_directory(ROOT / "data" / "weather_docs")
    results = store.search("为什么湿度高会觉得闷热 体感温度", top_k=2)
    assert results
    top_text = results[0].chunk.title + results[0].chunk.text
    assert "体感温度" in top_text or "热压力" in top_text


def test_intent_classification() -> None:
    assert classify_intent("北京今天适合跑步吗？") == "运动"
    assert classify_intent("农业喷药为什么要避开大风？") == "农业"
    assert detect_period("北京明天适合跑步吗？") == "tomorrow"


def test_weather_fetch_decision() -> None:
    assert should_fetch_weather("上海明天适合骑车吗？") is True
    assert should_fetch_weather("为什么湿度高会觉得闷热？") is False
    assert should_fetch_weather("厄尔尼诺是什么？") is False
    assert should_fetch_weather("副热带高压为什么会影响高温？") is False
    assert should_fetch_weather("广州明天适合骑车吗？") is True


def test_domain_guard() -> None:
    assert is_weather_domain_question("广州明天适合骑车吗？") is True
    assert is_weather_domain_question("厄尔尼诺是什么？") is True
    assert is_weather_domain_question("怎么做红烧肉？") is False
