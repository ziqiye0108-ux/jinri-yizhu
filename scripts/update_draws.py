from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup


YEAR = datetime.now().year
YEAR_PREFIX = str(YEAR)[-2:]
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / f"dlt_{YEAR}.json"
URL = "https://www.gdlottery.cn/f_html/kjgg/P085_{issue}.html"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DLTArchive/1.0)"}


def parse_prizes(html: str) -> dict[str, int]:
    soup = BeautifulSoup(html, "html.parser")
    prizes = {}
    for row in soup.select(".dlt_LotteryQk ul"):
        values = list(row.stripped_strings)
        if not values:
            continue
        level = next((v for v in values if re.fullmatch(r"[一二三四五六七八九]等奖", v)), None)
        if not level:
            continue
        amounts = [v for v in values if re.fullmatch(r"[\d,]+(?:\.\d+)?元", v)]
        if amounts:
            prizes[level] = int(float(amounts[0].replace(",", "").removesuffix("元")))
    return prizes


def fetch(issue_number: int) -> dict | None:
    issue = f"{YEAR_PREFIX}{issue_number:03d}"
    try:
        response = requests.get(URL.format(issue=issue), headers=HEADERS, timeout=15)
        if response.status_code != 200:
            return None
        response.encoding = "utf-8"
        text = re.sub(r"\s+", " ", response.text)
        date_match = re.search(r"开奖日期：(\d{4}年\d{1,2}月\d{1,2}日)", text)
        number_match = re.search(
            r"本期开奖号码：</li><li>([\d ]+)</li><li>([\d ]+)</li>", text
        )
        if not date_match or not number_match:
            return None
        draw_date = datetime.strptime(date_match.group(1), "%Y年%m月%d日").date()
        front = [int(value) for value in number_match.group(1).split()]
        back = [int(value) for value in number_match.group(2).split()]
        if len(front) != 5 or len(back) != 2:
            return None
        return {
            "issue": issue,
            "date": draw_date.isoformat(),
            "front": front,
            "back": back,
            "prizes": parse_prizes(response.text),
        }
    except (requests.RequestException, ValueError):
        return None


def main() -> None:
    if OUTPUT.exists():
        try:
            previous = json.loads(OUTPUT.read_text(encoding="utf-8")).get("draws", [])
            last_number = max(int(item["issue"][-3:]) for item in previous)
            upper_bound = min(160, last_number + 3)
        except (ValueError, KeyError, json.JSONDecodeError):
            upper_bound = min(160, int(datetime.now().timetuple().tm_yday * 3 / 7) + 8)
    else:
        upper_bound = min(160, int(datetime.now().timetuple().tm_yday * 3 / 7) + 8)
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(fetch, number) for number in range(1, upper_bound + 1)]
        draws = [result for future in as_completed(futures) if (result := future.result())]
    draws.sort(key=lambda item: item["issue"])
    if not draws:
        raise RuntimeError("未能从官方公告获取任何开奖数据，保留旧数据并退出")
    payload = {
        "game": "超级大乐透",
        "year": YEAR,
        "updatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": "https://www.gdlottery.cn/f_html/kjgg/",
        "draws": draws,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已保存 {len(draws)} 期数据到 {OUTPUT}")


if __name__ == "__main__":
    main()
