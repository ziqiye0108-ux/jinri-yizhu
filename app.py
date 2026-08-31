from flask import Flask, jsonify

app = Flask(__name__)


@app.get("/")
def index():
    return "<h1>今日一注</h1><p>预览版本准备中。</p>"


@app.get("/health")
def health():
    return jsonify({"status": "ok"})
