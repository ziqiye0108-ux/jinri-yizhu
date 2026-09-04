from __future__ import annotations

import hashlib
import json
import os
import secrets
from collections import Counter
from functools import lru_cache
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, render_template, request
from backtest import run_backtest

ROOT = Path(__file__).parent
DATA_FILE = ROOT / "data" / "dlt_2026.json"
BENCHMARK_FILE = ROOT / "data" / "random_benchmark_2022_2026.json"
MODEL_EXPERIMENT_FILE = ROOT / "data" / "model_experiment_2022_2026.json"
MULTIFACTOR_EXPERIMENT_FILE = ROOT / "data" / "multifactor_experiment_2022_2026.json"
DECOUPLED_EXPERIMENT_FILE = ROOT / "data" / "decoupled_experiment_2018_2026.json"
app = Flask(__name__)
PICK_WINDOW = 30
PICK_STRATEGY = "近30期：前区最冷5个 + 后区最冷1个/中间态1个"
DRAW_WEEKDAYS = {0, 2, 5}  # 周一、周三、周六
CHINA_TZ = ZoneInfo("Asia/Shanghai")


def local_today() -> date:
    return datetime.now(CHINA_TZ).date()


def upcoming_draw_dates(start: date, count: int = 6) -> list[dict]:
    labels = "一二三四五六日"
    result = []
    current = start
    while len(result) < count:
        if current.weekday() in DRAW_WEEKDAYS:
            result.append(
                {
                    "value": current.isoformat(),
                    "weekday": f"周{labels[current.weekday()]}",
                    "display": f"{current.month}月{current.day}日",
                }
            )
        current += timedelta(days=1)
    return result


def load_draws() -> list[dict]:
    draws = []
    for path in sorted((ROOT / "data").glob("dlt_20[0-9][0-9].json")):
        try:
            draws.extend(json.loads(path.read_text(encoding="utf-8")).get("draws", []))
        except json.JSONDecodeError:
            continue
    return sorted(draws, key=lambda item: item["issue"])


@lru_cache(maxsize=4)
def cached_experiment_report(data_mtime_ns: int) -> dict:
    draws = load_draws()
    report = run_backtest([draw for draw in draws if draw["date"] >= "2022-01-01"])
    report["benchmark"] = json.loads(BENCHMARK_FILE.read_text(encoding="utf-8"))
    report["model_experiment"] = json.loads(MODEL_EXPERIMENT_FILE.read_text(encoding="utf-8"))
    report["multifactor"] = json.loads(MULTIFACTOR_EXPERIMENT_FILE.read_text(encoding="utf-8"))
    report["decoupled"] = json.loads(DECOUPLED_EXPERIMENT_FILE.read_text(encoding="utf-8"))
    report["period_from"] = min(draw["date"] for draw in draws)
    report["period_to"] = max(draw["date"] for draw in draws)
    report["splits"] = {
        "training": sum(draw["date"][:4] in {"2022", "2023", "2024"} for draw in draws),
        "validation": sum(draw["date"].startswith("2025") for draw in draws),
        "holdout": sum(draw["date"].startswith("2026") for draw in draws),
    }
    return report


def _frequency_rank(
    history: list[dict], draw_date: str, key: str, size: int, nonce: int
) -> list[int]:
    """Rank numbers cold-to-hot with a stable date-based tie break."""
    frequencies = Counter(
        number for draw in history[-PICK_WINDOW:] for number in draw[key]
    )

    def rank_key(number: int) -> tuple[int, bytes]:
        tie_break = hashlib.sha256(
            f"cold-mid-v1|{draw_date}|{key}|{nonce}|{number}".encode()
        ).digest()
        return frequencies[number], tie_break

    return sorted(range(1, size + 1), key=rank_key)


def _cold_mid_pick(history: list[dict], draw_date: str, nonce: int = 0) -> dict:
    front_ranked = _frequency_rank(history, draw_date, "front", 35, nonce)
    back_ranked = _frequency_rank(history, draw_date, "back", 12, nonce)
    middle_index = 5 + int.from_bytes(
        hashlib.sha256(
            f"cold-mid-v1|{draw_date}|back-middle|{nonce}".encode()
        ).digest()[:2]
    ) % 2
    return {
        "front": sorted(front_ranked[:5]),
        "back": sorted([back_ranked[0], back_ranked[middle_index]]),
        "strategy": PICK_STRATEGY,
        "date_basis": f"开奖日前{min(PICK_WINDOW, len(history))}期频次",
    }


def recommendation(draw_date: str, draws: list[dict]) -> dict:
    existing = {
        tuple(item["front"] + item["back"])
        for item in draws
        if item.get("date", "").startswith(draw_date[:4])
    }
    prior_draws = [draw for draw in draws if draw.get("date", "") < draw_date]
    nonce = 0
    while True:
        result = _cold_mid_pick(prior_draws, draw_date, nonce)
        if tuple(result["front"] + result["back"]) not in existing:
            return {
                "front": result["front"],
                "back": result["back"],
                "strategy": result["strategy"],
                "dateBasis": result["date_basis"],
            }
        nonce += 1


@app.get("/")
def index():
    draws = load_draws()
    upcoming = upcoming_draw_dates(local_today(), count=1)
    return render_template(
        "index.html",
        upcoming=upcoming,
        draw_count=len(draws),
        latest=draws[-1] if draws else None,
    )


@app.post("/api/recommend")
def recommend():
    value = (request.get_json(silent=True) or {}).get("date", "")
    try:
        selected = datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return jsonify({"error": "请输入有效日期"}), 400
    today = local_today()
    if selected < today:
        return jsonify({"error": "请选择今天或未来的开奖日期"}), 400
    if selected.weekday() not in DRAW_WEEKDAYS:
        return jsonify({"error": "大乐透仅在周一、周三、周六开奖，请重新选择"}), 400
    next_draw = date.fromisoformat(upcoming_draw_dates(today, count=1)[0]["value"])
    if selected != next_draw:
        return jsonify({"error": f"当前仅支持最近开奖日：{next_draw.isoformat()}"}), 400
    draws = load_draws()
    return jsonify(
        {
            **recommendation(value, draws),
            "date": value,
            "checkedAgainst": len(draws),
            "year": selected.year,
            "notice": "号码仅供娱乐，按开奖日前30期冷热频次生成，不代表中奖预测或收益承诺。",
        }
    )


@app.get("/health")
def health():
    return jsonify({"status": "ok", "draws": len(load_draws())})


@app.get("/admin/backtest")
def admin_backtest():
    password = os.environ.get("ADMIN_PASSWORD")
    auth = request.authorization
    if not password or not auth or auth.username != "admin" or not secrets.compare_digest(auth.password, password):
        return ("需要后台授权", 401, {"WWW-Authenticate": 'Basic realm="Backtest"'})
    mtime = sum(path.stat().st_mtime_ns for path in (ROOT / "data").glob("dlt_20[0-9][0-9].json"))
    return render_template("admin_backtest.html", report=cached_experiment_report(mtime))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
