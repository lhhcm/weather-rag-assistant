from src.weather_rag.risk_engine import ActivityPlan, parse_plan, recommend_better_hours, score_risk_factors, select_activity_hours


def test_activity_risk_flags_storm_and_heat() -> None:
    plan = ActivityPlan(
        location="广州",
        activity_type="cycling",
        date="2026-06-26",
        start_time="18:00",
        duration_hours=2,
        people=4,
    )
    hourly = [
        {
            "time": "2026-06-26T18:00",
            "apparent_temperature": 38.5,
            "precip_probability": 93,
            "wind_speed": 10,
            "wind_gusts": 30,
            "uv_index": 2,
            "weather_code": 95,
            "weather": "雷暴",
        },
        {
            "time": "2026-06-26T19:00",
            "apparent_temperature": 36.0,
            "precip_probability": 85,
            "wind_speed": 8,
            "wind_gusts": 24,
            "uv_index": 0,
            "weather_code": 80,
            "weather": "阵雨",
        },
    ]
    factors = score_risk_factors(plan, hourly)
    names = {factor["name"] for factor in factors}
    assert {"降水", "雷暴/强对流", "高温体感"}.issubset(names)


def test_select_activity_hours() -> None:
    plan = ActivityPlan("上海", "running", "2026-06-26", "07:00", 2)
    hourly = [
        {"time": "2026-06-26T06:00"},
        {"time": "2026-06-26T07:00"},
        {"time": "2026-06-26T08:00"},
        {"time": "2026-06-26T09:00"},
    ]
    selected = select_activity_hours(hourly, plan)
    assert [row["time"] for row in selected] == ["2026-06-26T07:00", "2026-06-26T08:00"]


def test_parse_plan_prefers_specific_location() -> None:
    plan = parse_plan(
        {
            "location": "广州天河体育中心",
            "city": "广州",
            "activity_type": "cycling",
            "date": "2026-06-26",
            "start_time": "18:00",
        }
    )
    assert plan.location == "广州天河体育中心"


def test_recommend_better_hours_returns_time_windows() -> None:
    plan = ActivityPlan("广州", "cycling", "2026-06-26", "18:00", 2)
    hourly = [
        {
            "time": f"2026-06-26T{hour:02d}:00",
            "apparent_temperature": 28,
            "precip_probability": 10 if hour < 10 else 80,
            "wind_speed": 8,
            "wind_gusts": 12,
            "uv_index": 2,
            "weather_code": 3,
            "weather": "阴",
        }
        for hour in range(6, 12)
    ]

    windows = recommend_better_hours(hourly, plan)

    assert windows[0]["start"] == "2026-06-26T06:00"
    assert windows[0]["end"] == "2026-06-26T08:00"
