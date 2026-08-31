# 今日一注

仅供娱乐的大乐透号码生成器。输入未来日期后生成一注确定性随机号码，并与当年历史完整开奖号码去重。

历史数据来自广东省体育彩票中心的官方开奖公告，由 GitHub Actions 每天北京时间 00:00 自动更新。

## 本地运行

```bash
pip install -r requirements.txt
python scripts/update_draws.py
flask --app app run
```

## 测试

```bash
python -m unittest discover tests
```
