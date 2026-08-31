from __future__ import annotations

import hashlib
import json
import os
import secrets
from functools import lru_cache
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from backtest import build_experiment_report

ROOT = Path(__file__).parent
DATA_FILE = ROOT / "data" / "dlt_2026.json"
app = Flask(__name__)
DRAW_WEEKDAYS = {0, 2, 5}  # 周一、周三、周六


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
    try:
        payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        return payload.get("draws", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


@lru_cache(maxsize=4)
def cached_experiment_report(data_mtime_ns: int) -> dict:
    return build_experiment_report(load_draws())


def recommendation(draw_date: str, draws: list[dict]) -> dict:
    existing = {
        tuple(item["front"] + item["back"])
        for item in draws
        if item.get("date", "").startswith(draw_date[:4])
    }
    history_fingerprint = "|".join(
        f'{d["issue"]}:{",".join(map(str, d["front"] + d["back"]))}' for d in draws
    )
    nonce = 0
    while True:
        digest = hashlib.sha256(
            f"dlt-entertainment-v1|{draw_date}|{history_fingerprint}|{nonce}".encode()
        ).digest()
        front_pool = list(range(1, 36))
        back_pool = list(range(1, 13))
        front, back = [], []
        cursor = 0
        for _ in range(5):
            front.append(front_pool.pop(digest[cursor] % len(front_pool)))
            cursor += 1
        for _ in range(2):
            back.append(back_pool.pop(digest[cursor] % len(back_pool)))
            cursor += 1
        front.sort()
        back.sort()
        if tuple(front + back) not in existing:
            return {"front": front, "back": back}
        nonce += 1


@app.get("/")
def index():
    draws = load_draws()
    upcoming = upcoming_draw_dates(date.today())
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
    if selected < date.today():
        return jsonify({"error": "请选择今天或未来的开奖日期"}), 400
    if selected.weekday() not in DRAW_WEEKDAYS:
        return jsonify({"error": "大乐透仅在周一、周三、周六开奖，请重新选择"}), 400
    draws = load_draws()
    return jsonify(
        {
            **recommendation(value, draws),
            "date": value,
            "checkedAgainst": len(draws),
            "year": selected.year,
            "notice": "号码仅供娱乐，由确定性随机算法生成，不代表中奖预测。",
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
    mtime = DATA_FILE.stat().st_mtime_ns if DATA_FILE.exists() else 0
    return render_template("admin_backtest.html", report=cached_experiment_report(mtime))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
