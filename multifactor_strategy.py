from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from itertools import combinations
from math import log
from statistics import mean, pstdev

from backtest import prize_level


@dataclass(frozen=True)
class FusionConfig:
    name: str
    window: int
    frequency: float
    recent: float
    gap: float
    trend: float
    association: float
    structure: float


CANDIDATES = [
    FusionConfig("均衡融合", 80, .45, .25, .25, .25, .30, .35),
    FusionConfig("趋势增强", 60, .20, .55, -.15, .70, .25, .30),
    FusionConfig("均值回归", 100, -.25, .10, .75, -.35, .20, .40),
    FusionConfig("关联增强", 80, .25, .20, .20, .15, .85, .30),
    FusionConfig("形态增强", 100, .30, .20, .20, .15, .25, .90),
    FusionConfig("低自由度", 120, .50, 0, .20, 0, 0, .25),
]


def _zscore(values: dict[int, float]) -> dict[int, float]:
    center, spread = mean(values.values()), pstdev(values.values()) or 1
    return {key: (value - center) / spread for key, value in values.items()}


def _features(history: list[dict], key: str, size: int, window_size: int) -> dict[str, dict[int, float]]:
    window, recent = history[-window_size:], history[-12:]
    long_counts = Counter(n for draw in window for n in draw[key])
    recent_counts = Counter(n for draw in recent for n in draw[key])
    long_rate = {n: long_counts[n] / max(1, len(window)) for n in range(1, size + 1)}
    recent_rate = {n: recent_counts[n] / max(1, len(recent)) for n in range(1, size + 1)}
    gaps = {}
    for number in range(1, size + 1):
        gaps[number] = next((i for i, draw in enumerate(reversed(history)) if number in draw[key]), min(60, len(history)))
    trend = {n: recent_rate[n] - long_rate[n] for n in range(1, size + 1)}
    return {"frequency": _zscore(long_rate), "recent": _zscore(recent_rate),
            "gap": _zscore(gaps), "trend": _zscore(trend)}


def _pair_rates(history: list[dict], key: str, window_size: int) -> dict[tuple[int, int], float]:
    counts = Counter(pair for draw in history[-window_size:] for pair in combinations(sorted(draw[key]), 2))
    divisor = max(1, min(len(history), window_size))
    return {pair: count / divisor for pair, count in counts.items()}


def _shape_signature(combo: tuple[int, ...], size: int) -> tuple[int, int, int, int]:
    total_bin = sum(combo) // (10 if size == 35 else 4)
    odd = sum(n % 2 for n in combo)
    zones = len({min(2, (n - 1) * 3 // size) for n in combo})
    consecutive = sum(b == a + 1 for a, b in zip(combo, combo[1:]))
    return total_bin, odd, zones, consecutive


def _shape_rates(history: list[dict], key: str, size: int, window_size: int) -> Counter:
    return Counter(_shape_signature(tuple(sorted(draw[key])), size) for draw in history[-window_size:])


def _choose(history: list[dict], key: str, size: int, count: int, draw_date: str,
            config: FusionConfig) -> list[int]:
    features = _features(history, key, size, config.window)
    weights = {"frequency": config.frequency, "recent": config.recent,
               "gap": config.gap, "trend": config.trend}
    individual = {n: sum(weights[k] * features[k][n] for k in weights) for n in range(1, size + 1)}
    shortlist_size = 13 if size == 35 else 9
    tie = lambda n: int.from_bytes(sha256(f"fusion-v2|{draw_date}|{key}|{n}".encode()).digest()[:4])
    shortlist = sorted(range(1, size + 1), key=lambda n: (individual[n], tie(n)), reverse=True)[:shortlist_size]
    pairs = _pair_rates(history, key, config.window)
    shapes = _shape_rates(history, key, size, config.window)
    denom = max(1, min(len(history), config.window))

    def combo_score(combo: tuple[int, ...]) -> tuple[float, int]:
        pair_score = mean(pairs.get(pair, 0) for pair in combinations(combo, 2)) if count > 1 else 0
        shape_score = log((shapes[_shape_signature(combo, size)] + 1) / (denom + len(shapes) + 1))
        score = sum(individual[n] for n in combo) + config.association * pair_score * 20 + config.structure * shape_score
        digest = int.from_bytes(sha256(f"{draw_date}|{key}|{combo}".encode()).digest()[:4])
        return score, digest

    return list(max(combinations(sorted(shortlist), count), key=combo_score))


def fusion_pick(history: list[dict], draw_date: str, config: FusionConfig) -> dict:
    return {"front": _choose(history, "front", 35, 5, draw_date, config),
            "back": _choose(history, "back", 12, 2, draw_date, config), "model": config.name}


def evaluate(draws: list[dict], config: FusionConfig, years: set[str], warmup: int = 30) -> dict:
    rows, winners, prize_total, front_hits_total, back_hits_total = [], 0, 0, 0, 0
    for index, draw in enumerate(draws):
        if draw["date"][:4] not in years or index < warmup:
            continue
        pick = fusion_pick(draws[:index], draw["date"], config)
        front_hits = len(set(pick["front"]) & set(draw["front"]))
        back_hits = len(set(pick["back"]) & set(draw["back"]))
        level = prize_level(draw["issue"], front_hits, back_hits)
        prize = int(draw.get("prizes", {}).get(level, 0)) if level else 0
        winners += bool(level); prize_total += prize
        front_hits_total += front_hits; back_hits_total += back_hits
        rows.append({**draw, "pick": pick, "front_hits": front_hits, "back_hits": back_hits,
                     "level": level, "prize": prize})
    cost = len(rows) * 2
    return {"config": asdict(config), "draws": len(rows), "winners": winners, "cost": cost,
            "prize": prize_total, "profit": prize_total - cost,
            "roi": (prize_total - cost) / cost * 100 if cost else 0,
            "avg_front_hits": front_hits_total / len(rows), "avg_back_hits": back_hits_total / len(rows),
            "rows": rows}


def ablations(config: FusionConfig) -> list[FusionConfig]:
    return [
        replace(config, name="完整模型"),
        replace(config, name="去除时序", frequency=0, recent=0, gap=0, trend=0),
        replace(config, name="去除关联", association=0),
        replace(config, name="去除形态", structure=0),
    ]
