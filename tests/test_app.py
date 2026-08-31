import app as lottery_app


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

