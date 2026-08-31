from __future__ import annotations

from datetime import date
import random
from statistics import mean, median

from lunar_python import Solar


TRIGRAMS = {1: "乾", 2: "兑", 3: "离", 4: "震", 5: "巽", 6: "坎", 7: "艮", 8: "坤"}
METHOD_VERSION = "梅花易数·日期时辰法 v1"


def _mod(value: int, size: int) -> int:
    result = value % size
    return size if result == 0 else result


def zhouyi_pick(draw_date: str) -> dict:
    selected = date.fromisoformat(draw_date)
    lunar = Solar.fromYmd(selected.year, selected.month, selected.day).getLunar()
    year_branch = lunar.getYearZhiIndex() + 1
    lunar_month = abs(lunar.getMonth())
    lunar_day = lunar.getDay()
    hour_branch = 12  # 大乐透约21:25开奖，属亥时。
    upper = _mod(year_branch + lunar_month + lunar_day, 8)
    lower = _mod(year_branch + lunar_month + lunar_day + hour_branch, 8)
    moving = _mod(year_branch + lunar_month + lunar_day + hour_branch, 6)

    base = year_branch * 97 + lunar_month * 61 + lunar_day * 37 + upper * 19 + lower * 13 + moving
    front_ranked = sorted(
        range(1, 36),
        key=lambda n: ((base + n * (upper + moving + 5) + n * n * (lower + year_branch)) % 997, n),
    )
    back_ranked = sorted(
        range(1, 13),
        key=lambda n: ((base + n * (lower + moving + 3) + n * n * upper) % 389, n),
    )
    front = front_ranked[:5]
    back = back_ranked[:2]

    return {
        "front": sorted(front),
        "back": sorted(back),
        "upper": TRIGRAMS[upper],
        "lower": TRIGRAMS[lower],
        "moving": moving,
        "lunar": f"农历{lunar_month}月{lunar_day}日",
        "method": METHOD_VERSION,
    }


def prize_level(issue: str, front_hits: int, back_hits: int) -> str | None:
    hits = (front_hits, back_hits)
    if int(issue) < 19019:
        six_tier_rules = {
            (5, 2): "一等奖", (5, 1): "二等奖", (5, 0): "三等奖", (4, 2): "三等奖",
            (4, 1): "四等奖", (3, 2): "四等奖", (4, 0): "五等奖", (3, 1): "五等奖",
            (2, 2): "五等奖", (3, 0): "六等奖", (2, 1): "六等奖", (1, 2): "六等奖",
            (0, 2): "六等奖",
        }
        return six_tier_rules.get(hits)
    if int(issue) < 26014:
        old_rules = {
            (5, 2): "一等奖", (5, 1): "二等奖", (5, 0): "三等奖",
            (4, 2): "四等奖", (4, 1): "五等奖", (3, 2): "六等奖",
            (4, 0): "七等奖", (3, 1): "八等奖", (2, 2): "八等奖",
            (3, 0): "九等奖", (2, 1): "九等奖", (1, 2): "九等奖", (0, 2): "九等奖",
        }
        return old_rules.get(hits)
    new_rules = {
        (5, 2): "一等奖", (5, 1): "二等奖", (5, 0): "三等奖", (4, 2): "三等奖",
        (4, 1): "四等奖", (4, 0): "五等奖", (3, 2): "五等奖",
        (3, 1): "六等奖", (2, 2): "六等奖", (3, 0): "七等奖",
        (2, 1): "七等奖", (1, 2): "七等奖", (0, 2): "七等奖",
    }
    return new_rules.get(hits)


def run_backtest(draws: list[dict]) -> dict:
    rows = []
    total_prize = 0
    winners = 0
    for draw in draws:
        pick = zhouyi_pick(draw["date"])
        front_hits = len(set(pick["front"]) & set(draw["front"]))
        back_hits = len(set(pick["back"]) & set(draw["back"]))
        level = prize_level(draw["issue"], front_hits, back_hits)
        prize = int(draw.get("prizes", {}).get(level, 0)) if level else 0
        if level:
            winners += 1
            total_prize += prize
        rows.append({
            **draw,
            "pick": pick,
            "front_hits": front_hits,
            "back_hits": back_hits,
            "level": level,
            "prize": prize,
            "pick_front_text": " ".join(f"{n:02d}" for n in pick["front"]),
            "pick_back_text": " ".join(f"{n:02d}" for n in pick["back"]),
            "draw_front_text": " ".join(f"{n:02d}" for n in draw["front"]),
            "draw_back_text": " ".join(f"{n:02d}" for n in draw["back"]),
        })
    cost = len(rows) * 2
    return {
        "rows": list(reversed(rows)),
        "draws": len(rows),
        "winners": winners,
        "cost": cost,
        "prize": total_prize,
        "profit": total_prize - cost,
        "roi": ((total_prize - cost) / cost * 100) if cost else 0,
        "method": METHOD_VERSION,
    }


def run_random_benchmark(draws: list[dict], trials: int = 10_000, seed: int = 20260831) -> dict:
    rng = random.Random(seed)
    win_counts, prize_totals = [], []
    for _ in range(trials):
        wins = 0
        prize_total = 0
        for draw in draws:
            front = rng.sample(range(1, 36), 5)
            back = rng.sample(range(1, 13), 2)
            front_hits = len(set(front) & set(draw["front"]))
            back_hits = len(set(back) & set(draw["back"]))
            level = prize_level(draw["issue"], front_hits, back_hits)
            if level:
                wins += 1
                prize_total += int(draw.get("prizes", {}).get(level, 0))
        win_counts.append(wins)
        prize_totals.append(prize_total)
    win_sorted = sorted(win_counts)
    prize_sorted = sorted(prize_totals)

    def percentile(values: list[int], observed: float) -> float:
        return sum(value <= observed for value in values) / len(values) * 100

    def quantile(values: list[int], ratio: float) -> int:
        return values[min(len(values) - 1, int((len(values) - 1) * ratio))]

    return {
        "trials": trials, "seed": seed,
        "mean_wins": mean(win_counts), "median_wins": median(win_counts),
        "wins_p05": quantile(win_sorted, 0.05), "wins_p95": quantile(win_sorted, 0.95),
        "mean_prize": mean(prize_totals), "median_prize": median(prize_totals),
        "prize_p05": quantile(prize_sorted, 0.05), "prize_p95": quantile(prize_sorted, 0.95),
        "chance_profit": sum(value > len(draws) * 2 for value in prize_totals) / trials * 100,
        "win_counts": win_counts, "prize_totals": prize_totals,
        "wins_percentile": percentile(win_counts, 0), "prize_percentile": percentile(prize_totals, 0),
    }


def build_experiment_report(draws: list[dict]) -> dict:
    report = run_backtest(draws)
    benchmark = run_random_benchmark(draws)
    benchmark["wins_percentile"] = sum(v <= report["winners"] for v in benchmark["win_counts"]) / benchmark["trials"] * 100
    benchmark["prize_percentile"] = sum(v <= report["prize"] for v in benchmark["prize_totals"]) / benchmark["trials"] * 100
    report["benchmark"] = {k: v for k, v in benchmark.items() if k not in {"win_counts", "prize_totals"}}
    return report
