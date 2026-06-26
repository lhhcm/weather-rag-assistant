from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .assistant import action_advice, compose_answer
from .rag import SearchResult
from .weather_api import weather_summary


@dataclass
class LangChainAnswer:
    text: str
    backend: str
    llm_connected: bool
    model: str


class LangChainAnswerGenerator:
    """LangChain answer chain with an optional OpenAI-compatible LLM.

    The project can run without any API key. In that case LangChain still
    formats the prompt/context and then uses the deterministic local fallback.
    When WEATHER_LLM_API_KEY or OPENAI_API_KEY is configured, the same chain
    calls a real chat model through langchain-openai.
    """

    def __init__(self) -> None:
        load_dotenv_if_available()
        self.model_name = os.getenv("WEATHER_LLM_MODEL", "gpt-4o-mini")
        self.base_url = os.getenv("WEATHER_LLM_BASE_URL", "")
        self.api_key = os.getenv("WEATHER_LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
        self.local_chain = self._build_local_chain()
        self.chain = self._build_chain()

    @property
    def llm_connected(self) -> bool:
        return bool(self.api_key and self._chat_model_available())

    def generate(
        self,
        question: str,
        location: str,
        intent: str,
        period: str,
        weather: dict[str, Any] | None,
        weather_error: str,
        risks: list[dict[str, str]],
        results: list[SearchResult],
    ) -> LangChainAnswer:
        local_answer = compose_answer(question, location, intent, period, weather, weather_error, risks, results)
        context = build_answer_context(question, location, intent, period, weather, weather_error, risks, results, local_answer)
        if self.llm_connected and self.chain is not None:
            text = self.chain.invoke(context)
            return LangChainAnswer(text=str(text).strip(), backend="langchain-llm", llm_connected=True, model=self.model_name)

        text = self.local_chain.invoke(context) if self.local_chain is not None else local_answer
        return LangChainAnswer(text=text, backend="langchain-local-rag", llm_connected=False, model="local-template")

    def _build_local_chain(self):
        try:
            from langchain_core.runnables import RunnableLambda
        except ImportError:
            return None
        return RunnableLambda(lambda context: context["local_answer"])

    def _build_chain(self):
        if not self.llm_connected:
            return None
        try:
            from langchain_core.output_parsers import StrOutputParser
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_openai import ChatOpenAI
        except ImportError:
            return None

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是户外活动天气风险决策助手。必须基于给定天气数据和知识库来源回答，"
                    "不要编造没有提供的天气事实。回答要面向中国国内户外活动用户，"
                    "优先给出结论、依据、风险和可执行建议。",
                ),
                (
                    "human",
                    "用户问题：{question}\n"
                    "地点：{location}\n"
                    "意图：{intent}\n"
                    "时段：{period}\n"
                    "天气数据：{weather_text}\n"
                    "风险标签：{risk_text}\n"
                    "知识库来源：\n{source_text}\n\n"
                    "请用中文回答，结构为：结论、天气依据、知识依据、行动建议。"
                    "如果没有实时天气数据，要明确说明没有调用天气 API。"
                ),
            ]
        )
        kwargs: dict[str, Any] = {
            "model": self.model_name,
            "api_key": self.api_key,
            "temperature": 0.2,
        }
        if self.base_url:
            kwargs["base_url"] = self.base_url
        llm = ChatOpenAI(**kwargs)
        return prompt | llm | StrOutputParser()

    def _chat_model_available(self) -> bool:
        try:
            import langchain_openai  # noqa: F401
        except ImportError:
            return False
        return True


def build_answer_context(
    question: str,
    location: str,
    intent: str,
    period: str,
    weather: dict[str, Any] | None,
    weather_error: str,
    risks: list[dict[str, str]],
    results: list[SearchResult],
    local_answer: str,
) -> dict[str, str]:
    if weather:
        weather_text = weather_summary(weather, period)
    elif weather_error:
        weather_text = f"天气 API 错误：{weather_error}"
    else:
        weather_text = "本问题为气象知识解释问题，未调用实时天气 API。"

    risk_text = "、".join(f"{item['name']}：{item['reason']}" for item in risks) or "未触发明显天气风险"
    source_text = "\n".join(
        f"- {result.chunk.title} | {result.chunk.source} | 相似度 {result.score:.2f}\n  {result.chunk.text}"
        for result in results[:4]
    ) or "无检索结果"
    advice = action_advice(intent, weather, risks)

    return {
        "question": question,
        "location": location or "知识问答",
        "intent": intent,
        "period": period,
        "weather_text": weather_text,
        "risk_text": risk_text,
        "source_text": source_text,
        "advice": advice,
        "local_answer": local_answer,
    }


def build_chroma_retriever(docs_dir: Path, persist_dir: Path):
    try:
        from langchain_chroma import Chroma
        from langchain_community.document_loaders import DirectoryLoader, TextLoader
        from langchain_community.embeddings import HuggingFaceEmbeddings
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError as exc:  # pragma: no cover - optional dependency path.
        raise RuntimeError("请先执行 pip install -r requirements.txt") from exc

    loader = DirectoryLoader(
        str(docs_dir),
        glob="*.md",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
    )
    docs = loader.load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=80)
    chunks = splitter.split_documents(docs)
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    vector_db = Chroma.from_documents(chunks, embeddings, persist_directory=str(persist_dir))
    return vector_db.as_retriever(search_kwargs={"k": 4})


def load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()
