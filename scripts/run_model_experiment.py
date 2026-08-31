import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import load_draws
from backtest import run_random_benchmark
from model_strategy import CANDIDATES, walk_forward


def compact(report: dict) -> dict:
    return {key: value for key, value in report.items() if key != "rows"}


def random_baseline(draws: list[dict], observed: dict, seed: int) -> dict:
    result = run_random_benchmark(draws, trials=10_000, seed=seed)
    result["wins_percentile"] = sum(
        value <= observed["winners"] for value in result["win_counts"]
    ) / result["trials"] * 100
    result["prize_percentile"] = sum(
        value <= observed["prize"] for value in result["prize_totals"]
    ) / result["trials"] * 100
    return {key: value for key, value in result.items() if key not in {"win_counts", "prize_totals"}}


def main() -> None:
    draws = load_draws()
    training = [walk_forward(draws, config, {"2022", "2023", "2024"}) for config in CANDIDATES]
    # Training chooses the model once. Prize is the primary business metric; wins breaks ties.
    selected_training = max(training, key=lambda item: (item["prize"], item["winners"]))
    selected = next(config for config in CANDIDATES if config.name == selected_training["config"]["name"])
    validation = walk_forward(draws, selected, {"2025"})
    holdout = walk_forward(draws, selected, {"2026"})
    validation_draws = [draw for draw in draws if draw["date"].startswith("2025")]
    holdout_draws = [draw for draw in draws if draw["date"].startswith("2026")]
    output = {
        "method": "滚动时序集成 v1",
        "selection_rule": "仅按2022–2024训练集奖金选择，中奖期数用于同奖金额破同分",
        "candidates": [compact(item) for item in training],
        "selected": selected.name,
        "training": compact(selected_training),
        "validation": compact(validation),
        "holdout": compact(holdout),
        "random_validation": random_baseline(validation_draws, validation, 20250101),
        "random_holdout": random_baseline(holdout_draws, holdout, 20260101),
        "decision": "reject",
        "decision_reason": "验证集与留出集均未稳定优于随机基线，不进入前台选号",
    }
    path = ROOT / "data" / "model_experiment_2022_2026.json"
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
