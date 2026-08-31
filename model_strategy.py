from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, asdict
from hashlib import sha256
from statistics import mean, pstdev

from backtest import prize_level


@dataclass(frozen=True)
class ModelConfig:
    name: str
    window: int
    frequency: float
    recent: float
    gap: float
    trend: float


CANDIDATES = [
    ModelConfig("长期热度", 60, 1.0, 0.2, -0.1, 0.1),
    ModelConfig("短期趋势", 40, 0.2, 1.0, -0.2, 0.8),
    ModelConfig("均值回归", 80, -0.4, 0.1, 1.0, -0.4),
    ModelConfig("冷热平衡", 60, 0.4, -0.2, 0.5, 0.3),
    ModelConfig("长短集成", 100, 0.6, 0.5, 0.2, 0.4),
]


def _zscore(values: dict[int, float]) -> dict[int, float]:
    center = mean(values.values())
    spread = pstdev(values.values()) or 1
    return {number: (value - center) / spread for number, value in values.items()}


def _rank_pool(history: list[dict], key: str, size: int, count: int, draw_date: str,
               config: ModelConfig) -> list[int]:
    window = history[-config.window:]
    recent_window = history[-12:]
    frequencies = Counter(number for draw in window for number in draw[key])
    recent_frequencies = Counter(number for draw in recent_window for number in draw[key])
    gaps = {}
    for number in range(1, size + 1):
        gap = len(history)
        for index, draw in enumerate(reversed(history)):
            if number in draw[key]:
                gap = index
                break
        gaps[number] = min(gap, 60)

    long_rate = {n: frequencies[n] / max(1, len(window)) for n in range(1, size + 1)}
    recent_rate = {n: recent_frequencies[n] / max(1, len(recent_window)) for n in range(1, size + 1)}
    trend = {n: recent_rate[n] - long_rate[n] for n in range(1, size + 1)}
    parts = [_zscore(long_rate), _zscore(recent_rate), _zscore(gaps), _zscore(trend)]
    weights = [config.frequency, config.recent, config.gap, config.trend]

    def score(number: int) -> tuple[float, int]:
        value = sum(weight * part[number] for weight, part in zip(weights, parts))
        tie = int.from_bytes(sha256(f"{config.name}|{draw_date}|{key}|{number}".encode()).digest()[:4])
        return value, tie

    return sorted(range(1, size + 1), key=score, reverse=True)[:count]


def model_pick(history: list[dict], draw_date: str, config: ModelConfig) -> dict:
    return {
        "front": sorted(_rank_pool(history, "front", 35, 5, draw_date, config)),
        "back": sorted(_rank_pool(history, "back", 12, 2, draw_date, config)),
        "model": config.name,
    }


def walk_forward(draws: list[dict], config: ModelConfig, evaluate_years: set[str],
                 warmup: int = 30) -> dict:
    rows, winners, total_prize = [], 0, 0
    for index, draw in enumerate(draws):
        year = draw["date"][:4]
        if year not in evaluate_years or index < warmup:
            continue
        pick = model_pick(draws[:index], draw["date"], config)
        front_hits = len(set(pick["front"]) & set(draw["front"]))
        back_hits = len(set(pick["back"]) & set(draw["back"]))
        level = prize_level(draw["issue"], front_hits, back_hits)
        prize = int(draw.get("prizes", {}).get(level, 0)) if level else 0
        winners += bool(level)
        total_prize += prize
        rows.append({
            **draw, "pick": pick, "front_hits": front_hits, "back_hits": back_hits,
            "level": level, "prize": prize,
        })
    cost = len(rows) * 2
    return {
        "config": asdict(config), "draws": len(rows), "winners": winners,
        "cost": cost, "prize": total_prize, "profit": total_prize - cost,
        "roi": (total_prize - cost) / cost * 100 if cost else 0, "rows": rows,
    }
