import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import load_draws
from backtest import run_backtest, run_random_benchmark


def main() -> None:
    parser = argparse.ArgumentParser(description="Run and cache the reproducible random baseline.")
    parser.add_argument("--trials", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20260831)
    parser.add_argument("--output", default="data/random_benchmark_2022_2026.json")
    args = parser.parse_args()

    draws = load_draws()
    observed = run_backtest(draws)
    result = run_random_benchmark(draws, trials=args.trials, seed=args.seed)
    result["wins_percentile"] = sum(
        value <= observed["winners"] for value in result["win_counts"]
    ) / args.trials * 100
    result["prize_percentile"] = sum(
        value <= observed["prize"] for value in result["prize_totals"]
    ) / args.trials * 100
    result["period"] = {
        "from": min(draw["date"] for draw in draws),
        "to": max(draw["date"] for draw in draws),
        "draws": len(draws),
    }
    result = {key: value for key, value in result.items() if key not in {"win_counts", "prize_totals"}}

    output = ROOT / args.output
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
