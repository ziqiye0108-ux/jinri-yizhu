from __future__ import annotations

from datetime import date
from hashlib import sha256
from itertools import combinations
from math import log
from statistics import mean, pstdev

from lunar_python import Solar

from multifactor_strategy import FusionConfig, _features, _shape_rates, _shape_signature


METHOD = "多因子 80% + 日期卦象 20%"


def _normalize(values: dict[int, float]) -> dict[int, float]:
    center = mean(values.values())
    spread = pstdev(values.values()) or 1
    return {number: (value - center) / spread for number, value in values.items()}


def _date_numbers(draw_date: str) -> tuple[int, int, int, str]:
    selected = date.fromisoformat(draw_date)
    lunar = Solar.fromYmd(selected.year, selected.month, selected.day).getLunar()
    year_branch = lunar.getYearZhiIndex() + 1
    lunar_month, lunar_day, hour_branch = abs(lunar.getMonth()), lunar.getDay(), 12
    upper = (year_branch + lunar_month + lunar_day - 1) % 8 + 1
    lower = (year_branch + lunar_month + lunar_day + hour_branch - 1) % 8 + 1
    moving = (year_branch + lunar_month + lunar_day + hour_branch - 1) % 6 + 1
    label = f"农历{lunar_month}月{lunar_day}日 · {upper}/{lower}卦 · {moving}爻"
    return upper, lower, moving, label


def _select(history: list[dict], draw_date: str, key: str, size: int, count: int,
            pool_size: int, config: FusionConfig) -> list[int]:
    features = _features(history, key, size, config.window)
    weights = {"frequency": config.frequency, "recent": config.recent,
               "gap": config.gap, "trend": config.trend}
    statistical = _normalize({
        number: sum(weights[name] * features[name][number] for name in weights)
        for number in range(1, size + 1)
    })
    candidate_pool = sorted(statistical, key=lambda number: statistical[number], reverse=True)[:pool_size]
    upper, lower, moving, _ = _date_numbers(draw_date)
    start = (upper * 3 + lower + moving) % pool_size
    step = ((lower * 2 + moving) % (pool_size - 1)) + 1

    mystical_order = []
    for offset in range(pool_size):
        for hop in range(pool_size):
            number = candidate_pool[(start + offset + hop * step) % pool_size]
            if number not in mystical_order:
                mystical_order.append(number)
    mystical = _normalize({number: pool_size - rank for rank, number in enumerate(mystical_order)})

    shapes = _shape_rates(history, key, size, config.window)
    denominator = max(1, min(len(history), config.window))
    combo_list = list(combinations(sorted(candidate_pool), count))
    statistical_combo, mystical_combo = {}, {}
    for combo in combo_list:
        shape = log((shapes[_shape_signature(combo, size)] + 1) / (denominator + len(shapes) + 1))
        statistical_combo[combo] = sum(statistical[number] for number in combo) + config.structure * shape
        date_hash = int.from_bytes(sha256(f"hexagram|{draw_date}|{key}|{combo}".encode()).digest()[:4]) / 2**32
        mystical_combo[combo] = sum(mystical[number] for number in combo) + date_hash
    statistical_combo = _normalize(statistical_combo)
    mystical_combo = _normalize(mystical_combo)

    def combo_score(combo: tuple[int, ...]) -> tuple[float, int]:
        value = .8 * statistical_combo[combo] + .2 * mystical_combo[combo]
        tie = int.from_bytes(sha256(f"hybrid-v1|{draw_date}|{key}|{combo}".encode()).digest()[:4])
        return value, tie

    return list(max(combo_list, key=combo_score))


def hybrid_pick(history: list[dict], draw_date: str, config: FusionConfig) -> dict:
    _, _, _, lunar_label = _date_numbers(draw_date)
    return {
        "front": _select(history, draw_date, "front", 35, 5, 15, config),
        "back": _select(history, draw_date, "back", 12, 2, 8, config),
        "strategy": METHOD,
        "date_basis": lunar_label,
    }
