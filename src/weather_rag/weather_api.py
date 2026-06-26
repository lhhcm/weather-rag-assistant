from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


CITY_ALIASES = {
    "北京": "Beijing",
    "上海": "Shanghai",
    "广州": "Guangzhou",
    "深圳": "Shenzhen",
    "杭州": "Hangzhou",
    "南京": "Nanjing",
    "成都": "Chengdu",
    "重庆": "Chongqing",
    "武汉": "Wuhan",
    "西安": "Xi'an",
    "苏州": "Suzhou",
    "天津": "Tianjin",
    "青岛": "Qingdao",
    "厦门": "Xiamen",
    "长沙": "Changsha",
    "郑州": "Zhengzhou",
    "济南": "Jinan",
    "合肥": "Hefei",
    "福州": "Fuzhou",
    "昆明": "Kunming",
    "贵阳": "Guiyang",
    "南宁": "Nanning",
    "海口": "Haikou",
    "三亚": "Sanya",
    "哈尔滨": "Harbin",
    "长春": "Changchun",
    "沈阳": "Shenyang",
    "大连": "Dalian",
    "石家庄": "Shijiazhuang",
    "太原": "Taiyuan",
    "呼和浩特": "Hohhot",
    "兰州": "Lanzhou",
    "银川": "Yinchuan",
    "西宁": "Xining",
    "乌鲁木齐": "Urumqi",
    "拉萨": "Lhasa",
    "香港": "Hong Kong",
    "澳门": "Macau",
    "台北": "Taipei",
}

FOREIGN_CITY_TERMS = {
    "东京",
    "大阪",
    "首尔",
    "新加坡",
    "曼谷",
    "伦敦",
    "巴黎",
    "柏林",
    "纽约",
    "洛杉矶",
    "旧金山",
    "悉尼",
    "墨尔本",
    "Tokyo",
    "Seoul",
    "Singapore",
    "Bangkok",
    "London",
    "Paris",
    "Berlin",
    "New York",
    "Los Angeles",
    "Sydney",
}

SPECIAL_DOMESTIC_COUNTRY_CODES = {
    "香港": "HK",
    "澳门": "MO",
    "台北": "TW",
}

WEATHER_CODES = {
    0: "晴",
    1: "大部晴朗",
    2: "局部多云",
    3: "阴",
    45: "雾",
    48: "雾凇",
    51: "小毛毛雨",
    53: "中等毛毛雨",
    55: "强毛毛雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    80: "小阵雨",
    81: "中等阵雨",
    82: "强阵雨",
    95: "雷暴",
    96: "雷暴（可能伴冰雹）",
    99: "强雷暴（冰雹信号仅供参考）",
}


@dataclass
class Location:
    name: str
    display_name: str
    latitude: float
    longitude: float
    country: str = ""
    timezone: str = "auto"


LOCAL_PLACE_ALIASES = {
    "广州天河体育中心": Location("广州天河体育中心", "天河体育中心（广东省 / 广州市 / 天河区）", 23.1402, 113.3270, "中国", "Asia/Shanghai"),
    "天河体育中心": Location("天河体育中心", "天河体育中心（广东省 / 广州市 / 天河区）", 23.1402, 113.3270, "中国", "Asia/Shanghai"),
    "广州海珠湖": Location("广州海珠湖", "海珠湖（广东省 / 广州市 / 海珠区）", 23.0708, 113.3287, "中国", "Asia/Shanghai"),
    "海珠湖": Location("海珠湖", "海珠湖（广东省 / 广州市 / 海珠区）", 23.0708, 113.3287, "中国", "Asia/Shanghai"),
    "广州白云山": Location("广州白云山", "白云山（广东省 / 广州市 / 白云区）", 23.1850, 113.2970, "中国", "Asia/Shanghai"),
    "白云山": Location("白云山", "白云山（广东省 / 广州市 / 白云区）", 23.1850, 113.2970, "中国", "Asia/Shanghai"),
    "广州大学城": Location("广州大学城", "广州大学城（广东省 / 广州市 / 番禺区）", 23.0432, 113.3972, "中国", "Asia/Shanghai"),
    "广州番禺区": Location("广州番禺区", "番禺区（广东省 / 广州市）", 22.9377, 113.3841, "中国", "Asia/Shanghai"),
    "广州天河区": Location("广州天河区", "天河区（广东省 / 广州市）", 23.1246, 113.3612, "中国", "Asia/Shanghai"),
    "广州海珠区": Location("广州海珠区", "海珠区（广东省 / 广州市）", 23.0838, 113.3172, "中国", "Asia/Shanghai"),
    "广州白云区": Location("广州白云区", "白云区（广东省 / 广州市）", 23.1579, 113.2732, "中国", "Asia/Shanghai"),
}


class WeatherApiError(RuntimeError):
    pass


def detect_location(question: str, default_city: str | None = None) -> str:
    explicit_location = find_explicit_location(question)
    if explicit_location:
        return explicit_location

    default_city = default_city or os.getenv("DEFAULT_CITY", "上海")
    return default_city


def find_explicit_location(question: str) -> str | None:
    for city in CITY_ALIASES:
        if city in question:
            return city

    for city in FOREIGN_CITY_TERMS:
        if city.lower() in question.lower():
            return city

    english_match = re.search(r"\b(?:in|at|for)\s+([A-Z][a-zA-Z\- ]{2,24})", question)
    if english_match:
        return english_match.group(1).strip()
    return None


def _get_json(url: str, timeout: int = 8) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "weather-rag-assistant/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return json.loads(response.read().decode(charset))
    except Exception as exc:  # pragma: no cover - network failure is environment specific.
        raise WeatherApiError(str(exc)) from exc


def is_known_foreign_city(city: str) -> bool:
    normalized = city.lower().strip()
    return any(term.lower() == normalized for term in FOREIGN_CITY_TERMS)


def geocode_city(city: str) -> Location:
    if is_known_foreign_city(city):
        raise WeatherApiError(f"当前版本只支持中国国内城市，暂不支持国外城市：{city}")

    query = CITY_ALIASES.get(city, city)
    country_code = SPECIAL_DOMESTIC_COUNTRY_CODES.get(city, "CN")
    params = urllib.parse.urlencode(
        {
            "name": query,
            "count": 1,
            "language": "zh",
            "format": "json",
            "countryCode": country_code,
        }
    )
    payload = _get_json(f"https://geocoding-api.open-meteo.com/v1/search?{params}")
    results = payload.get("results") or []
    if not results:
        raise WeatherApiError(f"当前版本只支持中国国内城市，未找到国内城市：{city}")

    first = results[0]
    if first.get("country_code") != country_code:
        raise WeatherApiError(f"当前版本只支持中国国内城市：{city}")

    return Location(
        name=city,
        display_name=first.get("name") or city,
        latitude=float(first["latitude"]),
        longitude=float(first["longitude"]),
        country=first.get("country", ""),
        timezone=first.get("timezone", "auto"),
    )


def geocode_place(place: str) -> Location:
    cleaned = place.strip()
    if not cleaned:
        raise WeatherApiError("地点不能为空")
    coordinate_location = parse_coordinate_location(cleaned)
    if coordinate_location:
        return coordinate_location
    alias_location = find_local_place_alias(cleaned)
    if alias_location:
        return alias_location
    if cleaned in CITY_ALIASES or cleaned in SPECIAL_DOMESTIC_COUNTRY_CODES:
        return geocode_city(cleaned)
    if is_known_foreign_city(cleaned):
        raise WeatherApiError(f"当前版本只支持中国国内地点，暂不支持国外地点：{cleaned}")
    return geocode_query(cleaned, country_code="CN")


def parse_coordinate_location(text: str) -> Location | None:
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*[,，]\s*(-?\d+(?:\.\d+)?)", text)
    if not match:
        return None
    latitude = float(match.group(1))
    longitude = float(match.group(2))
    if not (3 <= latitude <= 54 and 73 <= longitude <= 136):
        raise WeatherApiError("坐标不在中国常用经纬度范围内，请检查纬度、经度顺序。")
    return Location(text, f"坐标地点（{latitude:.4f}, {longitude:.4f}）", latitude, longitude, "中国", "Asia/Shanghai")


def find_local_place_alias(text: str) -> Location | None:
    if text in LOCAL_PLACE_ALIASES:
        return LOCAL_PLACE_ALIASES[text]
    for key, location in LOCAL_PLACE_ALIASES.items():
        if key in text:
            return Location(text, location.display_name, location.latitude, location.longitude, location.country, location.timezone)
    return None


def geocode_query(query: str, country_code: str = "CN") -> Location:
    params = urllib.parse.urlencode(
        {
            "name": query,
            "count": 1,
            "language": "zh",
            "format": "json",
            "countryCode": country_code,
        }
    )
    payload = _get_json(f"https://geocoding-api.open-meteo.com/v1/search?{params}")
    results = payload.get("results") or []
    if not results:
        raise WeatherApiError(f"当前版本只支持中国国内地点，未找到：{query}")

    first = results[0]
    if first.get("country_code") != country_code:
        raise WeatherApiError(f"当前版本只支持中国国内地点：{query}")

    admin_parts = [first.get("admin1"), first.get("admin2"), first.get("admin3")]
    admin_text = " / ".join(part for part in admin_parts if part)
    display_name = first.get("name") or query
    if admin_text:
        display_name = f"{display_name}（{admin_text}）"

    return Location(
        name=query,
        display_name=display_name,
        latitude=float(first["latitude"]),
        longitude=float(first["longitude"]),
        country=first.get("country", ""),
        timezone=first.get("timezone", "auto"),
    )


def fetch_weather(city: str, target_date: str | None = None) -> dict[str, Any]:
    location = geocode_place(city)
    if target_date and is_past_date(target_date):
        return fetch_historical_weather(location, target_date)

    forecast_days = 7
    if target_date:
        forecast_days = max(7, min(16, (date.fromisoformat(target_date) - date.today()).days + 1))
    params = urllib.parse.urlencode(
        {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "timezone": "auto",
            "current": ",".join(
                [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "apparent_temperature",
                    "precipitation",
                    "weather_code",
                    "wind_speed_10m",
                    "wind_gusts_10m",
                ]
            ),
            "daily": ",".join(
                [
                    "weather_code",
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "apparent_temperature_max",
                    "precipitation_probability_max",
                    "wind_speed_10m_max",
                    "wind_gusts_10m_max",
                    "uv_index_max",
                ]
            ),
            "hourly": ",".join(
                [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "apparent_temperature",
                    "precipitation",
                    "precipitation_probability",
                    "weather_code",
                    "wind_speed_10m",
                    "wind_gusts_10m",
                    "uv_index",
                ]
            ),
            "forecast_days": forecast_days,
        }
    )
    payload = _get_json(f"https://api.open-meteo.com/v1/forecast?{params}")
    return normalize_weather(location, payload, "forecast")


def is_past_date(value: str) -> bool:
    try:
        return date.fromisoformat(value) < date.today()
    except ValueError:
        return False


def fetch_historical_weather(location: Location, target_date: str) -> dict[str, Any]:
    params = urllib.parse.urlencode(
        {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "timezone": location.timezone or "Asia/Shanghai",
            "start_date": target_date,
            "end_date": target_date,
            "daily": ",".join(
                [
                    "weather_code",
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "apparent_temperature_max",
                    "precipitation_sum",
                    "wind_speed_10m_max",
                    "wind_gusts_10m_max",
                ]
            ),
            "hourly": ",".join(
                [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "apparent_temperature",
                    "precipitation",
                    "weather_code",
                    "wind_speed_10m",
                    "wind_gusts_10m",
                ]
            ),
        }
    )
    payload = _get_json(f"https://archive-api.open-meteo.com/v1/archive?{params}")
    return normalize_weather(location, payload, "historical")


def normalize_weather(location: Location, payload: dict[str, Any], source_kind: str = "forecast") -> dict[str, Any]:
    current = payload.get("current", {})
    daily = payload.get("daily", {})
    hourly = payload.get("hourly", {})

    def daily_value(key: str, index: int = 0, default: Any = None) -> Any:
        values = daily.get(key) or []
        return values[index] if len(values) > index else default

    today = {
        "date": daily_value("time", 0),
        "weather": weather_label(daily_value("weather_code", 0)),
        "temp_max": daily_value("temperature_2m_max", 0),
        "temp_min": daily_value("temperature_2m_min", 0),
        "apparent_max": daily_value("apparent_temperature_max", 0),
        "precip_probability": daily_value("precipitation_probability_max", 0),
        "precipitation_sum": daily_value("precipitation_sum", 0),
        "wind_speed_max": daily_value("wind_speed_10m_max", 0),
        "wind_gusts_max": daily_value("wind_gusts_10m_max", 0),
        "uv_index_max": daily_value("uv_index_max", 0),
    }
    tomorrow = {
        "date": daily_value("time", 1),
        "weather": weather_label(daily_value("weather_code", 1)),
        "temp_max": daily_value("temperature_2m_max", 1),
        "temp_min": daily_value("temperature_2m_min", 1),
        "apparent_max": daily_value("apparent_temperature_max", 1),
        "precip_probability": daily_value("precipitation_probability_max", 1),
        "precipitation_sum": daily_value("precipitation_sum", 1),
        "wind_speed_max": daily_value("wind_speed_10m_max", 1),
        "wind_gusts_max": daily_value("wind_gusts_10m_max", 1),
        "uv_index_max": daily_value("uv_index_max", 1),
    }

    normalized = {
        "location": {
            "name": location.name,
            "display_name": location.display_name,
            "country": location.country,
            "latitude": location.latitude,
            "longitude": location.longitude,
        },
        "current": {
            "time": current.get("time"),
            "temperature": current.get("temperature_2m"),
            "humidity": current.get("relative_humidity_2m"),
            "apparent_temperature": current.get("apparent_temperature"),
            "precipitation": current.get("precipitation"),
            "weather": weather_label(current.get("weather_code")),
            "wind_speed": current.get("wind_speed_10m"),
            "wind_gusts": current.get("wind_gusts_10m"),
        },
        "today": today,
        "tomorrow": tomorrow,
        "hourly": normalize_hourly(hourly),
        "retrieved_at": datetime.now().isoformat(timespec="seconds"),
        "source_kind": source_kind,
    }
    normalized["risks"] = assess_risks(normalized)
    return normalized


def normalize_hourly(hourly: dict[str, Any]) -> list[dict[str, Any]]:
    times = hourly.get("time") or []

    def value_at(key: str, index: int) -> Any:
        values = hourly.get(key) or []
        return values[index] if len(values) > index else None

    rows: list[dict[str, Any]] = []
    for index, time_value in enumerate(times):
        rows.append(
            {
                "time": time_value,
                "temperature": value_at("temperature_2m", index),
                "humidity": value_at("relative_humidity_2m", index),
                "apparent_temperature": value_at("apparent_temperature", index),
                "precipitation": value_at("precipitation", index),
                "precip_probability": value_at("precipitation_probability", index),
                "weather": weather_label(value_at("weather_code", index)),
                "weather_code": value_at("weather_code", index),
                "wind_speed": value_at("wind_speed_10m", index),
                "wind_gusts": value_at("wind_gusts_10m", index),
                "uv_index": value_at("uv_index", index),
            }
        )
    return rows


def weather_label(code: Any) -> str:
    if code is None:
        return "未知"
    try:
        return WEATHER_CODES.get(int(code), f"天气代码 {code}")
    except (TypeError, ValueError):
        return "未知"


def assess_risks(weather: dict[str, Any], period: str = "today") -> list[dict[str, str]]:
    risks: list[dict[str, str]] = []
    current = weather.get("current", {}) if period == "today" else {}
    day = weather.get("tomorrow" if period == "tomorrow" else "today", {})

    apparent = _max_number(current.get("apparent_temperature"), day.get("apparent_max"))
    wind = _max_number(current.get("wind_speed"), current.get("wind_gusts"), day.get("wind_speed_max"), day.get("wind_gusts_max"))
    precip = _max_number(day.get("precip_probability"), 0)
    uv = _max_number(day.get("uv_index_max"), 0)
    temp_min = _min_number(day.get("temp_min"), current.get("temperature"))

    if apparent is not None and apparent >= 35:
        risks.append({"level": "high", "name": "高温体感", "reason": f"最高体感约 {apparent:g} 摄氏度"})
    if wind is not None and wind >= 39:
        risks.append({"level": "medium", "name": "强风", "reason": f"最大风速/阵风约 {wind:g} km/h"})
    if precip is not None and precip >= 60:
        risks.append({"level": "medium", "name": "降水", "reason": f"最高降水概率约 {precip:g}%"})
    if uv is not None and uv >= 6:
        risks.append({"level": "medium", "name": "紫外线", "reason": f"UV 指数约 {uv:g}"})
    if temp_min is not None and temp_min <= 0:
        risks.append({"level": "medium", "name": "低温/霜冻", "reason": f"最低温约 {temp_min:g} 摄氏度"})

    day_weather = str(day.get("weather", ""))
    if "雷暴" in day_weather:
        risks.append({"level": "high", "name": "雷暴/强对流", "reason": f"预报天气为{day_weather}"})

    if not risks:
        risks.append({"level": "low", "name": "常规", "reason": "未触发主要天气风险阈值"})
    return risks


def _max_number(*values: Any) -> float | None:
    numbers = [float(value) for value in values if isinstance(value, (int, float))]
    return max(numbers) if numbers else None


def _min_number(*values: Any) -> float | None:
    numbers = [float(value) for value in values if isinstance(value, (int, float))]
    return min(numbers) if numbers else None


def weather_summary(weather: dict[str, Any], period: str = "today") -> str:
    current = weather.get("current", {})
    day = weather.get("tomorrow" if period == "tomorrow" else "today", {})
    location = weather.get("location", {}).get("display_name", "目标城市")
    day_label = "明天" if period == "tomorrow" else "今日"
    day_summary = (
        f"{day_label}{day.get('weather', '未知')}，最高{day.get('temp_max', '未知')}摄氏度，"
        f"最低{day.get('temp_min', '未知')}摄氏度，最高降水概率{day.get('precip_probability', '未知')}%，"
        f"最大风速{day.get('wind_speed_max', '未知')} km/h，阵风{day.get('wind_gusts_max', '未知')} km/h，"
        f"UV 指数{day.get('uv_index_max', '未知')}。"
    )
    if period == "tomorrow":
        return f"{location}{day_summary}"

    return (
        f"{location}当前{current.get('weather', '未知')}，气温{current.get('temperature', '未知')}摄氏度，"
        f"体感{current.get('apparent_temperature', '未知')}摄氏度，湿度{current.get('humidity', '未知')}%，"
        f"风速{current.get('wind_speed', '未知')} km/h。"
        f"{day_summary}"
    )
