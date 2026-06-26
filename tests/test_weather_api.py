import pytest

from src.weather_rag.weather_api import WeatherApiError, assess_risks, detect_location, fetch_weather, geocode_city, geocode_place, weather_label


def test_detect_location() -> None:
    assert detect_location("北京明天适合跑步吗？") == "北京"
    assert detect_location("为什么湿度高会觉得闷热？", default_city="上海") == "上海"
    assert detect_location("东京明天适合骑车吗？") == "东京"


def test_weather_label() -> None:
    assert weather_label(0) == "晴"
    assert weather_label(95) == "雷暴"
    assert weather_label(99) == "强雷暴（冰雹信号仅供参考）"


def test_assess_risks() -> None:
    weather = {
        "current": {
            "temperature": 32,
            "apparent_temperature": 36,
            "wind_speed": 12,
            "wind_gusts": 20,
        },
        "today": {
            "temp_min": 26,
            "apparent_max": 37,
            "precip_probability": 75,
            "wind_speed_max": 18,
            "wind_gusts_max": 42,
            "uv_index_max": 8,
            "weather": "强雷暴（冰雹信号仅供参考）",
        },
    }
    names = {risk["name"] for risk in assess_risks(weather)}
    assert {"高温体感", "降水", "强风", "紫外线", "雷暴/强对流"}.issubset(names)


def test_geocode_restricts_to_china(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.weather_rag.weather_api as weather_api

    def fake_get_json(url: str, timeout: int = 8) -> dict:
        assert "countryCode=CN" in url
        return {"results": []}

    monkeypatch.setattr(weather_api, "_get_json", fake_get_json)
    with pytest.raises(WeatherApiError):
        geocode_city("东京")


def test_geocode_place_uses_query(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.weather_rag.weather_api as weather_api

    def fake_get_json(url: str, timeout: int = 8) -> dict:
        assert "countryCode=CN" in url
        return {
            "results": [
                {
                    "name": "天河体育中心",
                    "latitude": 23.138,
                    "longitude": 113.327,
                    "country": "中国",
                    "country_code": "CN",
                    "admin1": "广东省",
                    "admin2": "广州市",
                    "admin3": "天河区",
                    "timezone": "Asia/Shanghai",
                }
            ]
        }

    monkeypatch.setattr(weather_api, "_get_json", fake_get_json)
    location = geocode_place("广州越秀公园")
    assert location.latitude == 23.138
    assert "天河区" in location.display_name


def test_geocode_place_uses_local_alias() -> None:
    location = geocode_place("广州天河体育中心")
    assert location.latitude == pytest.approx(23.1402)
    assert "天河区" in location.display_name


def test_geocode_place_accepts_coordinates() -> None:
    location = geocode_place("23.1402,113.3270")
    assert location.longitude == pytest.approx(113.3270)


def test_fetch_weather_uses_archive_for_past_date(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.weather_rag.weather_api as weather_api

    def fake_get_json(url: str, timeout: int = 8) -> dict:
        assert "archive-api.open-meteo.com" in url
        assert "start_date=2020-01-01" in url
        return {
            "daily": {
                "time": ["2020-01-01"],
                "weather_code": [3],
                "temperature_2m_max": [20],
                "temperature_2m_min": [12],
                "apparent_temperature_max": [19],
                "precipitation_sum": [1.2],
                "wind_speed_10m_max": [12],
                "wind_gusts_10m_max": [20],
            },
            "hourly": {
                "time": ["2020-01-01T08:00"],
                "temperature_2m": [16],
                "relative_humidity_2m": [80],
                "apparent_temperature": [16],
                "precipitation": [1.2],
                "weather_code": [3],
                "wind_speed_10m": [8],
                "wind_gusts_10m": [14],
            },
        }

    monkeypatch.setattr(weather_api, "_get_json", fake_get_json)
    weather = fetch_weather("广州天河体育中心", "2020-01-01")
    assert weather["source_kind"] == "historical"
    assert weather["hourly"][0]["precipitation"] == 1.2
