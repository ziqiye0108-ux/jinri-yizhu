import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import load_draws
from backtest import run_random_benchmark
from multifactor_strategy import CANDIDATES, ablations, evaluate


def compact(report):
    return {key: value for key, value in report.items() if key != "rows"}


def baseline(draws, observed, seed):
    result = run_random_benchmark(draws, trials=10_000, seed=seed)
    result["wins_percentile"] = sum(v <= observed["winners"] for v in result["win_counts"]) / result["trials"] * 100
    result["prize_percentile"] = sum(v <= observed["prize"] for v in result["prize_totals"]) / result["trials"] * 100
    return {k: v for k, v in result.items() if k not in {"win_counts", "prize_totals"}}


def main():
    draws = load_draws()
    validation_years = {"2023", "2024", "2025"}
    candidates = [evaluate(draws, config, validation_years) for config in CANDIDATES]
    # Prefer consistent hit signal over a single rare high prize, then use prize as tie-breaker.
    selected_report = max(candidates, key=lambda r: (r["winners"], r["avg_front_hits"] + r["avg_back_hits"], r["prize"]))
    selected = next(c for c in CANDIDATES if c.name == selected_report["config"]["name"])
    yearly = {year: compact(evaluate(draws, selected, {year})) for year in ["2023", "2024", "2025"]}
    holdout = evaluate(draws, selected, {"2026"})
    validation_draws = [d for d in draws if d["date"][:4] in validation_years]
    holdout_draws = [d for d in draws if d["date"].startswith("2026")]
    output = {
        "method": "多因子融合 v2", "decision": "reject",
        "selection_rule": "2023–2025滚动验证优先比较中奖稳定性与平均命中，奖金仅破同分",
        "selected": selected.name,
        "candidates": [compact(r) for r in candidates],
        "validation": compact(selected_report), "yearly": yearly,
        "ablations": [compact(evaluate(draws, config, validation_years)) for config in ablations(selected)],
        "holdout": compact(holdout),
        "random_validation": baseline(validation_draws, selected_report, 20230501),
        "random_holdout": baseline(holdout_draws, holdout, 20260501),
    }
    rv, rh = output["random_validation"], output["random_holdout"]
    passes = (selected_report["winners"] > rv["mean_wins"] and rh["wins_percentile"] >= 60
              and sum(row["winners"] >= row["draws"] * rv["mean_wins"] / len(validation_draws)
                      for row in yearly.values()) >= 2)
    output["decision"] = "pass" if passes else "reject"
    output["decision_reason"] = ("通过预设门槛，可进入候选观察" if passes else
        "未同时满足跨年度稳定、验证集优于随机、留出集不低于随机第60百分位，拒绝接入前台")
    (ROOT / "data" / "multifactor_experiment_2022_2026.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
