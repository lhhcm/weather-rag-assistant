from __future__ import annotations

import re
from typing import Any

from .rag import LocalVectorStore, SearchResult
from .weather_api import (
    WeatherApiError,
    assess_risks,
    detect_location,
    fetch_weather,
    find_explicit_location,
    weather_summary,
)


INTENT_KEYWORDS = {
    "通勤": ["通勤", "上班", "出门", "地铁", "堵车", "雨伞", "带伞"],
    "运动": ["跑步", "骑车", "骑行", "健身", "运动", "徒步"],
    "户外": ["露营", "登山", "户外", "野餐", "活动", "比赛"],
    "农业": ["农业", "作物", "农田", "喷药", "施肥", "霜冻", "采收"],
    "防灾": ["雷暴", "大风", "强降雨", "内涝", "危险", "预警", "强对流"],
    "科普": ["为什么", "是什么", "解释", "原理", "区别", "术语", "概念"],
}

METEOROLOGY_TERMS = [
    "厄尔尼诺",
    "拉尼娜",
    "enso",
    "南方涛动",
    "副热带高压",
    "西太平洋副高",
    "季风",
    "梅雨",
    "锋面",
    "冷锋",
    "暖锋",
    "准静止锋",
    "露点",
    "湿球温度",
    "体感温度",
    "热指数",
    "风寒",
    "强对流",
    "雷暴",
    "冰雹",
    "龙卷",
    "台风",
    "热带气旋",
    "气压",
    "等压线",
    "位势高度",
    "逆温",
    "边界层",
    "能见度",
    "相对湿度",
    "降水概率",
    "短临预报",
    "数值预报",
]

WEATHER_DECISION_TERMS = [
    "天气",
    "下雨",
    "雨",
    "降雨",
    "降水",
    "温度",
    "气温",
    "体感",
    "风",
    "紫外线",
    "湿度",
    "要带伞",
    "带伞",
    "雨伞",
    "淋雨",
    "积水",
    "晒",
    "防晒",
    "热不热",
    "冷不冷",
    "闷热",
    "潮湿",
    "穿什么",
]

TIME_TERMS = ["今天", "明天", "后天", "现在", "当前", "实时", "未来", "周末", "今晚", "早上", "下午", "晚上"]

OUTDOOR_WEATHER_TERMS = [
    "骑行",
    "骑车",
    "跑步",
    "徒步",
    "登山",
    "露营",
    "野餐",
    "户外",
    "出行",
    "出门",
    "通勤",
    "上班",
    "上学",
    "活动",
    "比赛",
    "训练",
    "遛娃",
    "遛狗",
    "散步",
    "拍照",
    "郊游",
    "爬山",
    "路线",
    "安全",
    "风险",
    "取消",
    "改期",
]

GENERIC_DECISION_TERMS = ["适合", "能不能", "可以", "要不要", "建议", "推荐"]

OUT_OF_SCOPE_TOPIC_TERMS = [
    "吃",
    "饭",
    "菜",
    "猪脚饭",
    "火锅",
    "奶茶",
    "咖啡",
    "做饭",
    "红烧肉",
    "电影",
    "游戏",
    "股票",
    "基金",
    "代码",
    "编程",
    "数学题",
    "历史",
    "旅游攻略",
    "酒店",
    "买房",
    "装修",
]

OUT_OF_SCOPE_ANSWER = (
    "我主要回答户外活动天气风险、国内地点天气决策和气象专业术语问题。"
    "你可以这样问：广州明天适合骑行吗？广州明天出门吃饭要带伞吗？雷暴天气为什么不适合露营？厄尔尼诺是什么？"
)


class WeatherRagAssistant:
    def __init__(self, vector_store: LocalVectorStore | None = None) -> None:
        self.vector_store = vector_store or LocalVectorStore.from_directory()

    def ask(self, question: str) -> dict[str, Any]:
        cleaned_question = question.strip()
        if not cleaned_question:
            return {"error": "问题不能为空"}
        if not is_weather_domain_question(cleaned_question):
            return {
                "answer": OUT_OF_SCOPE_ANSWER,
                "location": "非天气问题",
                "intent": "非天气领域",
                "period": detect_period(cleaned_question),
                "weather": None,
                "weather_error": "",
                "risks": [],
                "sources": [],
            }

        fetch_required = should_fetch_weather(cleaned_question)
        city = detect_location(cleaned_question) if fetch_required else ""
        intent = classify_intent(cleaned_question)
        period = detect_period(cleaned_question)
        weather: dict[str, Any] | None = None
        weather_error = ""
        risks: list[dict[str, str]] = []

        if fetch_required:
            try:
                weather = fetch_weather(city)
                risks = assess_risks(weather, period)
            except WeatherApiError as exc:
                weather_error = str(exc)

        retrieval_query = build_retrieval_query(cleaned_question, intent, period, weather, risks)
        results = self.vector_store.search(retrieval_query, top_k=4)
        answer = compose_answer(cleaned_question, city, intent, period, weather, weather_error, risks, results)

        return {
            "answer": answer,
            "location": city or "知识问答",
            "intent": intent,
            "period": period,
            "weather": weather,
            "weather_error": weather_error,
            "risks": risks,
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


def classify_intent(question: str) -> str:
    if is_meteorology_concept_question(question):
        return "科普"
    for intent, keywords in INTENT_KEYWORDS.items():
        if any(keyword in question for keyword in keywords):
            return intent
    return "综合"


def detect_period(question: str) -> str:
    if "明天" in question or "明日" in question:
        return "tomorrow"
    return "today"


def is_meteorology_concept_question(question: str) -> bool:
    lower = question.lower()
    return any(term.lower() in lower for term in METEOROLOGY_TERMS)


def is_weather_domain_question(question: str) -> bool:
    lower = question.lower()
    explicit_location = find_explicit_location(question)
    has_weather_term = any(term in question for term in WEATHER_DECISION_TERMS)
    has_outdoor_term = any(term in question for term in OUTDOOR_WEATHER_TERMS)
    has_generic_decision = any(term in question for term in GENERIC_DECISION_TERMS)
    has_out_of_scope_topic = any(term in question for term in OUT_OF_SCOPE_TOPIC_TERMS)
    has_time_term = any(term in question for term in TIME_TERMS)
    asks_definition = any(term in question for term in ["是什么", "为什么", "解释", "原理", "区别", "概念", "术语"])
    concept_question = is_meteorology_concept_question(question)

    if concept_question:
        return True
    if has_weather_term:
        return True
    if has_out_of_scope_topic and has_generic_decision and not has_outdoor_term:
        return False
    if has_outdoor_term and (has_time_term or explicit_location or asks_definition):
        return True
    if explicit_location and has_time_term and has_generic_decision:
        return False
    if "weather" in lower:
        return True
    return False


def should_fetch_weather(question: str) -> bool:
    """Only fetch live weather when the user asks about a concrete place/time decision."""
    lower = question.lower()
    explicit_location = find_explicit_location(question)
    has_decision_term = any(term in question for term in WEATHER_DECISION_TERMS)
    has_outdoor_term = any(term in question for term in OUTDOOR_WEATHER_TERMS)
    has_time_term = any(term in question for term in TIME_TERMS)
    asks_definition = any(term in question for term in ["是什么", "为什么", "解释", "原理", "区别", "概念", "术语"])
    concept_question = is_meteorology_concept_question(question)

    if concept_question and asks_definition and not explicit_location:
        return False
    if concept_question and not explicit_location and not has_time_term:
        return False
    if explicit_location and (has_decision_term or (has_outdoor_term and has_time_term)):
        return True
    if "weather" in lower and explicit_location:
        return True
    return False


def build_retrieval_query(
    question: str,
    intent: str,
    period: str,
    weather: dict[str, Any] | None,
    risks: list[dict[str, str]],
) -> str:
    parts = [question, intent]
    if weather:
        parts.append(weather_summary(weather, period))
        risk_names = " ".join(risk["name"] for risk in risks)
        parts.append(risk_names)
    return "\n".join(parts)


def compose_answer(
    question: str,
    city: str,
    intent: str,
    period: str,
    weather: dict[str, Any] | None,
    weather_error: str,
    risks: list[dict[str, str]],
    results: list[SearchResult],
) -> str:
    lines: list[str] = []

    if weather:
        risk_text = "、".join(f"{item['name']}({item['reason']})" for item in risks)
        conclusion = decide_conclusion(question, intent, risks)
        lines.append(f"结论：{conclusion}")
        lines.append(f"天气依据：{weather_summary(weather, period)}")
        lines.append(f"风险标签：{risk_text}")
    elif weather_error:
        if "只支持中国国内城市" in weather_error:
            lines.append(f"结论：{weather_error}。请换成国内城市，例如广州、上海、北京、成都。")
        else:
            lines.append(f"结论：我已检索气象知识库，但实时天气 API 暂时不可用，建议稍后刷新。错误信息：{weather_error}")
    else:
        lines.append("结论：这是气象知识解释问题，不需要调用城市实时天气；我会优先依据知识库解释概念。")

    if results:
        evidence = "；".join(f"{result.chunk.title}（相似度 {result.score:.2f}）" for result in results[:3])
        lines.append(f"知识依据：{evidence}。")

    lines.append(f"行动建议：{action_advice(intent, weather, risks)}")
    lines.append("说明：天气决策类问题会调用国内城市天气 API；术语解释类问题只走气象知识库，避免默认成上海天气。")
    return "\n".join(lines)


def decide_conclusion(question: str, intent: str, risks: list[dict[str, str]]) -> str:
    risk_names = {risk["name"] for risk in risks if risk.get("level") != "low"}
    if not risk_names:
        if intent in {"运动", "户外", "通勤"} or re.search(r"适合|能不能|可以", question):
            return "整体风险不高，可以安排，但仍建议关注临近预报。"
        return "当前没有触发明显天气风险，可结合具体场景做常规安排。"

    if "雷暴/强对流" in risk_names or "雷暴" in risk_names or "强风" in risk_names:
        return "存在户外安全风险，不建议安排高强度户外或骑行活动。"
    if "降水" in risk_names:
        return "存在较明显降水风险，出行需要雨具并预留时间。"
    if "高温体感" in risk_names:
        return "热压力偏高，应减少正午户外活动并做好补水。"
    if "紫外线" in risk_names:
        return "紫外线偏强，户外活动需要防晒。"
    if "低温/霜冻" in risk_names:
        return "低温风险需要关注保暖，农业场景需防霜冻。"
    return "存在一定天气风险，建议降低活动强度并准备备选方案。"


def action_advice(
    intent: str,
    weather: dict[str, Any] | None,
    risks: list[dict[str, str]] | None = None,
) -> str:
    base = {
        "通勤": "带好雨具或防晒用品，给交通留出 10-20 分钟缓冲。",
        "运动": "优先选择清晨或傍晚，若有强风、降水或高温体感，降低配速和时长。",
        "户外": "准备备选室内方案，雷暴、强风和高降水概率时避免露营、登山和水上活动。",
        "农业": "关注最低温、降水窗口和风速，喷药施肥尽量避开大风和降雨时段。",
        "防灾": "远离低洼积水、临时构筑物和孤立高物，必要时推迟活动。",
        "科普": "把它当成背景知识理解即可；若要判断某个城市的出行影响，请再补充国内城市和日期。",
        "综合": "结合问题类型判断：术语解释看知识库，具体出行看城市天气数据。",
    }
    advice = base.get(intent, base["综合"])
    if not weather:
        return advice

    risk_names = {risk["name"] for risk in (risks if risks is not None else weather.get("risks", []))}
    additions = []
    if "降水" in risk_names:
        additions.append("携带雨具，避开低洼路段。")
    if "强风" in risk_names:
        additions.append("避免骑行、临水和搭帐篷。")
    if "雷暴/强对流" in risk_names:
        additions.append("雷声或闪电出现时尽快进入室内，避免树下、空旷地和水边。")
    if "高温体感" in risk_names:
        additions.append("补水并减少正午暴晒。")
    if "紫外线" in risk_names:
        additions.append("使用防晒霜、帽子和太阳镜。")
    if "低温/霜冻" in risk_names:
        additions.append("注意保暖，农作物做好覆盖防护。")
    return advice + (" " + " ".join(additions) if additions else "")


def trim_text(text: str, max_length: int) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    return compact if len(compact) <= max_length else compact[: max_length - 1] + "…"


def health_payload(assistant: WeatherRagAssistant) -> dict[str, Any]:
    answer_generator = getattr(assistant, "answer_generator", None)
    llm_connected = bool(getattr(answer_generator, "llm_connected", False))
    llm_model = getattr(answer_generator, "model_name", "local-template") if llm_connected else "local-template"
    return {
        "status": "ok",
        "documents": len(assistant.vector_store.chunks),
        "vector_backend": "local-hash",
        "orchestrator": "langgraph" if getattr(assistant, "graph_enabled", False) else "linear-fallback",
        "answer_backend": "langchain-llm" if llm_connected else "langchain-local-rag",
        "llm": {
            "connected": llm_connected,
            "model": llm_model,
        },
        "graph_nodes": getattr(assistant, "graph_nodes", []),
        "sample_questions": [
            "广州明天适合骑车吗？",
            "厄尔尼诺是什么？",
            "副热带高压为什么会影响高温？",
            "露点温度和相对湿度有什么区别？",
        ],
    }
