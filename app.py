from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request

ROOT = Path(__file__).parent
DATA_FILE = ROOT / "data" / "dlt_2026.json"
app = Flask(__name__)


def load_draws() -> list[dict]:
    try:
        payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        return payload.get("draws", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


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
    return render_template(
        "index.html",
        today=date.today().isoformat(),
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
