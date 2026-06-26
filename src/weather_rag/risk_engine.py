from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from .weather_api import WeatherApiError, fetch_weather


ACTIVITY_TYPES = {
    "cycling": "骑行",
    "running": "跑步",
    "camping": "露营",
    "hiking": "徒步/登山",
    "outdoor_event": "户外活动运营",
    "parent_child": "亲子出行",
}

ACTIVITY_WEIGHTS = {
    "cycling": {"precip": 28, "storm": 36, "wind": 22, "heat": 10, "uv": 4},
    "running": {"precip": 18, "storm": 32, "wind": 10, "heat": 28, "uv": 12},
    "camping": {"precip": 30, "storm": 36, "wind": 24, "heat": 5, "uv": 5},
    "hiking": {"precip": 24, "storm": 38, "wind": 18, "heat": 12, "uv": 8},
    "outdoor_event": {"precip": 26, "storm": 34, "wind": 18, "heat": 12, "uv": 10},
    "parent_child": {"precip": 22, "storm": 36, "wind": 12, "heat": 20, "uv": 10},
}


@dataclass
class ActivityPlan:
    location: str
    activity_type: str
    date: str
    start_time: str
    duration_hours: float
    people: int = 1
    children: bool = False


def evaluate_activity_plan(payload: dict[str, Any]) -> dict[str, Any]:
    plan = parse_plan(payload)
    weather = fetch_weather(plan.location, plan.date)
    hourly = select_activity_hours(weather.get("hourly", []), plan)
    if not hourly:
        raise WeatherApiError("未找到该时间段的小时级天气数据。未来预报通常支持未来 16 天内；过去日期按历史天气回放查询。")

    risk_factors = score_risk_factors(plan, hourly)
    vetoes = build_vetoes(risk_factors)
    score = max(0, 100 - sum(item["points"] for item in risk_factors))
    level = decide_level(score, vetoes)
    conclusion = build_conclusion(plan, level, vetoes)

    return {
        "plan": {
            "city": plan.location,
            "location": plan.location,
            "resolved_location": weather.get("location"),
            "activity_type": plan.activity_type,
            "activity_label": ACTIVITY_TYPES.get(plan.activity_type, plan.activity_type),
            "date": plan.date,
            "start_time": plan.start_time,
            "duration_hours": plan.duration_hours,
            "people": plan.people,
            "children": plan.children,
        },
        "score": round(score),
        "level": level,
        "conclusion": conclusion,
        "risk_factors": risk_factors,
        "vetoes": vetoes,
        "weather_window": summarize_window(hourly),
        "best_hours": recommend_better_hours(weather.get("hourly", []), plan),
        "contingency": build_contingency(plan, risk_factors, vetoes),
        "notification": build_notification(plan, level, vetoes),
        "data_source": {
            "provider": data_provider(weather),
            "retrieved_at": weather.get("retrieved_at"),
            "location": weather.get("location"),
            "kind": weather.get("source_kind", "forecast"),
            "note": data_source_note(weather),
        },
    }


def parse_plan(payload: dict[str, Any]) -> ActivityPlan:
    location = str(payload.get("location") or payload.get("city") or "").strip()
    if not location:
        raise ValueError("地点不能为空")

    activity_type = str(payload.get("activity_type", "outdoor_event")).strip() or "outdoor_event"
    if activity_type not in ACTIVITY_TYPES:
        activity_type = "outdoor_event"

    date = str(payload.get("date", "")).strip()
    start_time = str(payload.get("start_time", "")).strip()
    if not date or not start_time:
        raise ValueError("活动日期和开始时间不能为空")

    duration_hours = float(payload.get("duration_hours", 2) or 2)
    duration_hours = min(max(duration_hours, 1), 12)
    people = int(payload.get("people", 1) or 1)
    people = max(1, people)
    children = bool(payload.get("children", False))
    return ActivityPlan(location, activity_type, date, start_time, duration_hours, people, children)


def select_activity_hours(hourly: list[dict[str, Any]], plan: ActivityPlan) -> list[dict[str, Any]]:
    start = datetime.fromisoformat(f"{plan.date}T{plan.start_time}")
    end = start + timedelta(hours=plan.duration_hours)
    selected = []
    for row in hourly:
        row_time = datetime.fromisoformat(row["time"])
        if start <= row_time < end:
            selected.append(row)
    return selected


def score_risk_factors(plan: ActivityPlan, hourly: list[dict[str, Any]]) -> list[dict[str, Any]]:
    weights = ACTIVITY_WEIGHTS.get(plan.activity_type, ACTIVITY_WEIGHTS["outdoor_event"])
    max_precip = max_number(row.get("precip_probability") for row in hourly)
    max_precip_amount = max_number(row.get("precipitation") for row in hourly)
    max_gust = max_number(row.get("wind_gusts") for row in hourly)
    max_wind = max_number(row.get("wind_speed") for row in hourly)
    max_apparent = max_number(row.get("apparent_temperature") for row in hourly)
    max_uv = max_number(row.get("uv_index") for row in hourly)
    storm_hours = [row for row in hourly if is_storm(row)]

    factors: list[dict[str, Any]] = []
    if max_precip >= 80:
        factors.append(factor("降水", weights["precip"], "high", f"活动时段最高降水概率 {max_precip:g}%"))
    elif max_precip >= 60:
        factors.append(factor("降水", weights["precip"] * 0.75, "medium", f"活动时段最高降水概率 {max_precip:g}%"))
    elif max_precip >= 40:
        factors.append(factor("降水", weights["precip"] * 0.45, "low", f"活动时段最高降水概率 {max_precip:g}%"))
    elif max_precip_amount >= 8:
        factors.append(factor("降水", weights["precip"], "high", f"活动时段最大小时降水量 {max_precip_amount:g} mm"))
    elif max_precip_amount >= 2.5:
        factors.append(factor("降水", weights["precip"] * 0.75, "medium", f"活动时段最大小时降水量 {max_precip_amount:g} mm"))
    elif max_precip_amount > 0:
        factors.append(factor("降水", weights["precip"] * 0.35, "low", f"活动时段出现降水 {max_precip_amount:g} mm"))

    if storm_hours:
        factors.append(factor("雷暴/强对流", weights["storm"], "high", "活动时段出现雷暴或强对流天气代码"))

    wind_value = max(max_gust, max_wind)
    if wind_value >= 39:
        factors.append(factor("强风", weights["wind"], "high", f"活动时段最大风速/阵风 {wind_value:g} km/h"))
    elif wind_value >= 28:
        factors.append(factor("风偏大", weights["wind"] * 0.55, "medium", f"活动时段最大风速/阵风 {wind_value:g} km/h"))

    if max_apparent >= 38:
        factors.append(factor("高温体感", weights["heat"], "high", f"最高体感温度 {max_apparent:g} 摄氏度"))
    elif max_apparent >= 35:
        factors.append(factor("高温体感", weights["heat"] * 0.75, "medium", f"最高体感温度 {max_apparent:g} 摄氏度"))
    elif max_apparent <= 2:
        factors.append(factor("低温体感", weights["heat"] * 0.6, "medium", f"最低体感温度 {max_apparent:g} 摄氏度"))

    if max_uv >= 8:
        factors.append(factor("强紫外线", weights["uv"], "medium", f"最高 UV 指数 {max_uv:g}"))
    elif max_uv >= 6:
        factors.append(factor("紫外线", weights["uv"] * 0.55, "low", f"最高 UV 指数 {max_uv:g}"))

    if plan.children and any(item["level"] in {"medium", "high"} for item in factors):
        factors.append(factor("儿童敏感人群", 8, "medium", "计划包含儿童，天气风险阈值需要更保守"))
    if plan.people >= 30 and any(item["level"] == "high" for item in factors):
        factors.append(factor("多人组织风险", 8, "medium", "参与人数较多，撤离和通知成本更高"))

    return factors or [factor("常规", 0, "low", "活动时段未触发主要天气风险阈值")]


def factor(name: str, points: float, level: str, reason: str) -> dict[str, Any]:
    return {"name": name, "points": round(points, 1), "level": level, "reason": reason}


def build_vetoes(factors: list[dict[str, Any]]) -> list[str]:
    vetoes = []
    names = {item["name"] for item in factors}
    if "雷暴/强对流" in names:
        vetoes.append("雷暴/强对流为户外活动一票否决项")
    if any(item["name"] == "降水" and item["level"] == "high" for item in factors):
        vetoes.append("高降水概率触发改期/备用方案阈值")
    if any(item["name"] == "强风" and item["level"] == "high" for item in factors):
        vetoes.append("强风触发户外设施和骑行安全阈值")
    return vetoes


def decide_level(score: float, vetoes: list[str]) -> str:
    if vetoes or score < 55:
        return "不推荐"
    if score < 75:
        return "谨慎"
    return "适合"


def build_conclusion(plan: ActivityPlan, level: str, vetoes: list[str]) -> str:
    label = ACTIVITY_TYPES.get(plan.activity_type, plan.activity_type)
    if level == "不推荐":
        reason = "；".join(vetoes) if vetoes else "综合风险偏高"
        return f"{plan.location}{plan.date} {plan.start_time} 的{label}不推荐按原计划进行，原因：{reason}。"
    if level == "谨慎":
        return f"{plan.location}{plan.date} {plan.start_time} 的{label}可以保留计划，但需要准备备用方案并临近复查。"
    return f"{plan.location}{plan.date} {plan.start_time} 的{label}整体适合开展，按常规防晒/补水/雨具准备即可。"


def summarize_window(hourly: list[dict[str, Any]]) -> dict[str, Any]:
    has_precip_probability = any(isinstance(row.get("precip_probability"), (int, float)) for row in hourly)
    return {
        "start": hourly[0]["time"],
        "end": hourly[-1]["time"],
        "has_precip_probability": has_precip_probability,
        "max_precip_probability": max_number(row.get("precip_probability") for row in hourly),
        "max_precipitation": max_number(row.get("precipitation") for row in hourly),
        "max_apparent_temperature": max_number(row.get("apparent_temperature") for row in hourly),
        "max_wind_or_gust": max(max_number(row.get("wind_speed") for row in hourly), max_number(row.get("wind_gusts") for row in hourly)),
        "max_uv_index": max_number(row.get("uv_index") for row in hourly),
        "weather_labels": sorted({str(row.get("weather")) for row in hourly if row.get("weather")}),
        "weather_codes": sorted({int(row["weather_code"]) for row in hourly if isinstance(row.get("weather_code"), (int, float))}),
        "hours": hourly,
    }


def recommend_better_hours(hourly: list[dict[str, Any]], plan: ActivityPlan) -> list[dict[str, Any]]:
    same_day = [row for row in hourly if str(row.get("time", "")).startswith(plan.date)]
    candidates = []
    window_size = max(1, int(round(plan.duration_hours)))
    for index, row in enumerate(same_day):
        start = datetime.fromisoformat(row["time"])
        end = start + timedelta(hours=plan.duration_hours)
        if not (6 <= start.hour <= 21) or end.hour > 22:
            continue
        window = same_day[index : index + window_size]
        if len(window) < window_size:
            continue
        risk = max(simple_hour_risk(item) for item in window)
        labels = sorted({str(item.get("weather")) for item in window if item.get("weather")})
        candidates.append(
            {
                "time": row["time"],
                "start": row["time"],
                "end": end.isoformat(timespec="minutes"),
                "score": max(0, 100 - risk),
                "weather": "、".join(labels[:2]) if labels else row.get("weather"),
            }
        )
    candidates.sort(key=lambda item: item["score"], reverse=True)
    return candidates[:3]


def simple_hour_risk(row: dict[str, Any]) -> float:
    risk = 0.0
    risk += min(float(row.get("precip_probability") or 0), 100) * 0.35
    risk += min(float(row.get("precipitation") or 0), 20) * 3
    risk += max(0, float(row.get("apparent_temperature") or 20) - 32) * 4
    risk += max(0, float(row.get("wind_gusts") or row.get("wind_speed") or 0) - 24) * 2
    risk += max(0, float(row.get("uv_index") or 0) - 6) * 3
    if is_storm(row):
        risk += 50
    return risk


def build_contingency(plan: ActivityPlan, factors: list[dict[str, Any]], vetoes: list[str]) -> list[str]:
    suggestions = []
    names = {item["name"] for item in factors}
    if vetoes:
        suggestions.append("准备取消/改期阈值：雷暴预警、降水概率大于 80%、阵风大于 39 km/h 任一出现即改期。")
    if "降水" in names:
        suggestions.append("准备雨具、防滑鞋和室内集合点，避免低洼积水路段。")
    if "强风" in names or "风偏大" in names:
        suggestions.append("取消帐篷、展架、骑行等受风影响大的安排，检查固定物。")
    if "高温体感" in names:
        suggestions.append("避开正午，增加补水点、遮阴点和中暑观察。")
    if "强紫外线" in names or "紫外线" in names:
        suggestions.append("准备防晒霜、帽子、太阳镜，儿童和长时户外需减少暴露。")
    if not suggestions:
        suggestions.append("常规准备：补水、防晒、基础雨具，并在活动前 2 小时复查天气。")
    return suggestions


def build_notification(plan: ActivityPlan, level: str, vetoes: list[str]) -> str:
    label = ACTIVITY_TYPES.get(plan.activity_type, plan.activity_type)
    if level == "不推荐":
        return f"【活动天气提醒】{plan.location}{plan.date} {plan.start_time} 的{label}天气风险偏高，建议改期或启用室内备用方案。主要原因：{'；'.join(vetoes) or '综合天气风险偏高'}。"
    if level == "谨慎":
        return f"【活动天气提醒】{plan.location}{plan.date} {plan.start_time} 的{label}可暂时保留，但请携带雨具/防晒用品，并在活动前 2 小时复查天气。"
    return f"【活动天气提醒】{plan.location}{plan.date} {plan.start_time} 的{label}当前天气条件整体可行，请按常规准备补水、防晒和基础雨具。"


def is_storm(row: dict[str, Any]) -> bool:
    code = row.get("weather_code")
    try:
        return int(code) in {95, 96, 99}
    except (TypeError, ValueError):
        return "雷暴" in str(row.get("weather", ""))


def max_number(values) -> float:
    numbers = [float(value) for value in values if isinstance(value, (int, float))]
    return max(numbers) if numbers else 0.0


def data_provider(weather: dict[str, Any]) -> str:
    if weather.get("source_kind") == "historical":
        return "Open-Meteo Historical Weather API"
    return "Open-Meteo Forecast API"


def data_source_note(weather: dict[str, Any]) -> str:
    if weather.get("source_kind") == "historical":
        return "基于真实历史小时级天气数据回放；过去日期不是天气预报。"
    return "基于真实小时级天气预报计算；结果随预报更新变化。"
