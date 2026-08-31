import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import load_draws
from decoupled_strategy import (BACK_CANDIDATES, FRONT_CANDIDATES, evaluate,
                                evaluate_zone, permutation_test)


def compact(report):
    return {key: value for key, value in report.items() if key != "rows"}


def main():
    # The official Guangdong archive is incomplete before mid-2017, so v3 starts at 2018.
    draws = [draw for draw in load_draws() if draw["date"] >= "2018-01-01"]
    selection_years = {"2018", "2019", "2020", "2021", "2022"}
    fronts = [evaluate_zone(draws, config, "front", selection_years) for config in FRONT_CANDIDATES]
    backs = [evaluate_zone(draws, config, "back", selection_years) for config in BACK_CANDIDATES]
    chosen_front_report = max(fronts, key=lambda r: (r["average_hits"], -r["annual_std"]))
    chosen_back_report = max(backs, key=lambda r: (r["average_hits"], -r["annual_std"]))
    chosen_front = next(c for c in FRONT_CANDIDATES if c.name == chosen_front_report["config"]["name"])
    chosen_back = next(c for c in BACK_CANDIDATES if c.name == chosen_back_report["config"]["name"])
    windows = {
        "selection_2018_2022": evaluate(draws, chosen_front, chosen_back, selection_years),
        "recheck_2023_2024": evaluate(draws, chosen_front, chosen_back, {"2023", "2024"}),
        "recheck_2025": evaluate(draws, chosen_front, chosen_back, {"2025"}),
        "final_2026": evaluate(draws, chosen_front, chosen_back, {"2026"}),
    }
    recheck_rows = windows["recheck_2023_2024"]["rows"] + windows["recheck_2025"]["rows"] + windows["final_2026"]["rows"]
    output = {
        "method": "前后区解耦多因子 v3", "period": {"from": draws[0]["date"], "to": draws[-1]["date"], "draws": len(draws)},
        "data_note": "2017官方归档仅覆盖6月以后，本轮为避免不完整年度偏差，从2018开始。",
        "selection_rule": "前区、后区分别按2018–2022平均命中选择；同分时优先年度波动更低。共现因子权重固定为0。",
        "front_candidates": fronts, "back_candidates": backs,
        "selected_front": chosen_front.name, "selected_back": chosen_back.name,
        "windows": {key: compact(value) for key, value in windows.items()},
        "permutation": permutation_test(recheck_rows),
    }
    p = output["permutation"]
    stable = p["win_percentile"] >= 95 and p["hit_percentile"] >= 95
    output["decision"] = "candidate" if stable else "reject"
    output["decision_reason"] = ("置换检验的中奖与总命中均达到95百分位，保留候选但仍不等于盈利预测" if stable else
        "未同时通过中奖次数与总命中的95百分位置换门槛，不进入前台")
    (ROOT / "data" / "decoupled_experiment_2018_2026.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))

if __name__ == "__main__": main()
