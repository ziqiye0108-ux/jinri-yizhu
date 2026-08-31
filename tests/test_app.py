import app as lottery_app
from datetime import date


def test_recommendation_is_valid_and_not_in_history():
    draws = [{"issue": "26001", "date": "2026-01-01", "front": [1, 2, 3, 4, 5], "back": [1, 2]}]
    result = lottery_app.recommendation("2026-09-02", draws)
    assert len(result["front"]) == 5
    assert len(set(result["front"])) == 5
    assert all(1 <= n <= 35 for n in result["front"])
    assert len(result["back"]) == 2
    assert len(set(result["back"])) == 2
    assert all(1 <= n <= 12 for n in result["back"])
    assert result != {"front": [1, 2, 3, 4, 5], "back": [1, 2]}


def test_same_date_is_stable():
    assert lottery_app.recommendation("2026-09-02", []) == lottery_app.recommendation("2026-09-02", [])


def test_health_endpoint():
    client = lottery_app.app.test_client()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json["status"] == "ok"


def test_upcoming_dates_only_use_draw_weekdays():
    days = lottery_app.upcoming_draw_dates(date(2026, 8, 31))
    assert len(days) == 6
    assert all(date.fromisoformat(day["value"]).weekday() in {0, 2, 5} for day in days)


def test_non_draw_day_is_rejected():
    client = lottery_app.app.test_client()
    response = client.post("/api/recommend", json={"date": "2026-09-04"})
    assert response.status_code == 400


def test_zhouyi_pick_is_deterministic_and_valid():
    from backtest import zhouyi_pick
    first = zhouyi_pick("2026-08-31")
    second = zhouyi_pick("2026-08-31")
    assert first == second
    assert len(first["front"]) == len(set(first["front"])) == 5
    assert len(first["back"]) == len(set(first["back"])) == 2
    assert all(1 <= n <= 35 for n in first["front"])
    assert all(1 <= n <= 12 for n in first["back"])


def test_prize_rules_cover_old_and_new_versions():
    from backtest import prize_level
    assert prize_level("26013", 4, 2) == "四等奖"
    assert prize_level("26014", 4, 2) == "三等奖"
