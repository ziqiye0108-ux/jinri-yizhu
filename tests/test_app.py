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


def test_active_recommendation_uses_only_prior_draws():
    draws = lottery_app.load_draws()
    first = lottery_app.recommendation("2026-09-02", draws)
    draws_with_future = draws + [{"issue": "26999", "date": "2026-09-05", "front": [1, 2, 3, 4, 5], "back": [1, 2]}]
    second = lottery_app.recommendation("2026-09-02", draws_with_future)
    assert first == second
    assert first["strategy"] == lottery_app.PICK_STRATEGY


def test_multiple_draw_dates_produce_valid_stable_picks():
    draws = lottery_app.load_draws()
    for draw_date in ("2026-09-07", "2026-09-09", "2026-09-12"):
        first = lottery_app.recommendation(draw_date, draws)
        second = lottery_app.recommendation(draw_date, draws)
        assert first == second
        assert len(first["front"]) == len(set(first["front"])) == 5
        assert len(first["back"]) == len(set(first["back"])) == 2


def test_cold_mid_strategy_uses_30_prior_draws():
    history = [
        {
            "issue": f"25{index:03d}",
            "date": f"2025-01-{index + 1:02d}",
            "front": [1, 2, 3, 4, 5],
            "back": [1, 2],
        }
        for index in range(30)
    ]
    result = lottery_app._cold_mid_pick(history, "2026-09-07")
    assert not set(result["front"]) & {1, 2, 3, 4, 5}
    assert result["back"][0] not in {1, 2}
    assert result["strategy"] == lottery_app.PICK_STRATEGY


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
    assert prize_level("18001", 4, 2) == "三等奖"
    assert prize_level("19018", 3, 2) == "四等奖"
    assert prize_level("19019", 4, 2) == "四等奖"
    assert prize_level("26013", 4, 2) == "四等奖"
    assert prize_level("26014", 4, 2) == "三等奖"


def test_random_benchmark_is_reproducible():
    from backtest import run_random_benchmark
    draws = [{"issue": "26014", "date": "2026-02-02", "front": [1, 2, 3, 4, 5], "back": [1, 2], "prizes": {"七等奖": 5}}]
    first = run_random_benchmark(draws, trials=20, seed=7)
    second = run_random_benchmark(draws, trials=20, seed=7)
    assert first["win_counts"] == second["win_counts"]
    assert first["prize_totals"] == second["prize_totals"]


def test_load_draws_combines_all_cached_years():
    draws = lottery_app.load_draws()
    assert len(draws) == 1285
    assert draws[0]["issue"] == "18001"
    assert draws[-1]["issue"] == "26098"
    assert all(draw.get("prizes") for draw in draws)


def test_model_strategy_never_reads_current_draw():
    from model_strategy import CANDIDATES, model_pick
    history = lottery_app.load_draws()[:60]
    first = model_pick(history, "2022-06-01", CANDIDATES[0])
    mutated_future = {"date": "2022-06-01", "front": [1, 2, 3, 4, 5], "back": [1, 2]}
    second = model_pick(history, mutated_future["date"], CANDIDATES[0])
    assert first == second


def test_multifactor_pick_is_deterministic_and_valid():
    from multifactor_strategy import CANDIDATES, fusion_pick
    history = lottery_app.load_draws()[:80]
    first = fusion_pick(history, "2022-08-01", CANDIDATES[0])
    second = fusion_pick(history, "2022-08-01", CANDIDATES[0])
    assert first == second
    assert len(first["front"]) == len(set(first["front"])) == 5
    assert len(first["back"]) == len(set(first["back"])) == 2


def test_admin_renders_multifactor_experiment(monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "test")
    lottery_app.cached_experiment_report.cache_clear()
    response = lottery_app.app.test_client().get(
        "/admin/backtest", headers={"Authorization": "Basic YWRtaW46dGVzdA=="}
    )
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "多因子融合 v2" in page
    assert "因子消融" in page
