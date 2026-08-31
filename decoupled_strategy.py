from __future__ import annotations

from dataclasses import asdict, dataclass
import random
from statistics import mean, pstdev

from backtest import prize_level
from multifactor_strategy import FusionConfig, _choose


@dataclass(frozen=True)
class ZoneConfig:
    name: str
    window: int
    frequency: float
    recent: float
    gap: float
    trend: float
    structure: float

    def fusion(self) -> FusionConfig:
        return FusionConfig(self.name, self.window, self.frequency, self.recent,
                            self.gap, self.trend, 0, self.structure)


FRONT_CANDIDATES = [
    ZoneConfig("前区均值回归", 100, -.25, .10, .75, -.35, .40),
    ZoneConfig("前区低自由度", 120, .50, 0, .20, 0, .25),
    ZoneConfig("前区温和趋势", 80, .30, .25, .10, .25, .35),
    ZoneConfig("前区遗漏优先", 60, 0, 0, 1.0, 0, .30),
]
BACK_CANDIDATES = [
    ZoneConfig("后区均值回归", 80, -.20, .10, .80, -.30, .25),
    ZoneConfig("后区低自由度", 120, .45, 0, .20, 0, .20),
    ZoneConfig("后区温和趋势", 60, .20, .35, .10, .30, .20),
    ZoneConfig("后区遗漏优先", 50, 0, 0, 1.0, 0, .15),
]


def zone_pick(history: list[dict], draw_date: str, key: str, config: ZoneConfig) -> list[int]:
    size, count = (35, 5) if key == "front" else (12, 2)
    return _choose(history, key, size, count, draw_date, config.fusion())


def decoupled_pick(history: list[dict], draw_date: str, front: ZoneConfig, back: ZoneConfig) -> dict:
    return {"front": zone_pick(history, draw_date, "front", front),
            "back": zone_pick(history, draw_date, "back", back),
            "model": f"{front.name} + {back.name}"}


def evaluate_zone(draws: list[dict], config: ZoneConfig, key: str, years: set[str], warmup: int = 30) -> dict:
    yearly: dict[str, list[int]] = {}
    for index, draw in enumerate(draws):
        year = draw["date"][:4]
        if year not in years or index < warmup:
            continue
        pick = zone_pick(draws[:index], draw["date"], key, config)
        yearly.setdefault(year, []).append(len(set(pick) & set(draw[key])))
    annual_means = {year: mean(values) for year, values in yearly.items()}
    return {"config": asdict(config), "average_hits": mean(v for values in yearly.values() for v in values),
            "annual_means": annual_means, "annual_std": pstdev(annual_means.values()) if len(annual_means) > 1 else 0}


def evaluate(draws: list[dict], front: ZoneConfig, back: ZoneConfig, years: set[str], warmup: int = 30) -> dict:
    rows, winners, prize_total, front_total, back_total = [], 0, 0, 0, 0
    for index, draw in enumerate(draws):
        if draw["date"][:4] not in years or index < warmup:
            continue
        pick = decoupled_pick(draws[:index], draw["date"], front, back)
        fh, bh = len(set(pick["front"]) & set(draw["front"])), len(set(pick["back"]) & set(draw["back"]))
        level = prize_level(draw["issue"], fh, bh)
        prize = int(draw.get("prizes", {}).get(level, 0)) if level else 0
        winners += bool(level); prize_total += prize; front_total += fh; back_total += bh
        rows.append({"issue": draw["issue"], "date": draw["date"], "pick": pick,
                     "front": draw["front"], "back": draw["back"], "front_hits": fh,
                     "back_hits": bh, "level": level, "prize": prize, "prizes": draw.get("prizes", {})})
    cost = len(rows) * 2
    return {"front_config": asdict(front), "back_config": asdict(back), "draws": len(rows),
            "winners": winners, "prize": prize_total, "cost": cost, "profit": prize_total - cost,
            "roi": (prize_total - cost) / cost * 100 if cost else 0,
            "avg_front_hits": front_total / len(rows), "avg_back_hits": back_total / len(rows), "rows": rows}


def permutation_test(rows: list[dict], trials: int = 2_000, seed: int = 20260901) -> dict:
    rng = random.Random(seed)
    observed_wins = sum(bool(row["level"]) for row in rows)
    observed_hits = sum(row["front_hits"] + row["back_hits"] for row in rows)
    win_values, hit_values = [], []
    by_year = {}
    for row in rows:
        by_year.setdefault(row["date"][:4], []).append(row)
    for _ in range(trials):
        wins = hits = 0
        for year_rows in by_year.values():
            outcomes = year_rows[:]
            rng.shuffle(outcomes)
            for prediction, outcome in zip(year_rows, outcomes):
                fh = len(set(prediction["pick"]["front"]) & set(outcome["front"]))
                bh = len(set(prediction["pick"]["back"]) & set(outcome["back"]))
                hits += fh + bh
                wins += bool(prize_level(outcome["issue"], fh, bh))
        win_values.append(wins); hit_values.append(hits)
    return {"trials": trials, "seed": seed, "observed_wins": observed_wins,
            "mean_permuted_wins": mean(win_values),
            "win_percentile": sum(v <= observed_wins for v in win_values) / trials * 100,
            "observed_hits": observed_hits, "mean_permuted_hits": mean(hit_values),
            "hit_percentile": sum(v <= observed_hits for v in hit_values) / trials * 100}
