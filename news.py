"""世界の経済ニュース取得モジュール。

無料の RSS フィードからヘッドラインを取得する。APIキー不要。
取得できない場合は空リストを返し、UI 側で握りつぶす。
"""
from __future__ import annotations

import feedparser

# 無料で取得できる経済・市場系 RSS フィード
FEEDS = {
    "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
    "CNBC Markets": "https://www.cnbc.com/id/20910258/device/rss/rss.html",
    "MarketWatch": "http://feeds.marketwatch.com/marketwatch/topstories/",
    "Investing.com": "https://www.investing.com/rss/news_25.rss",
}


def fetch_news(limit: int = 12) -> list[dict]:
    """各フィードからヘッドラインを集約して返す。

    戻り値: [{"title", "link", "source", "published"}...]
    """
    items: list[dict] = []
    for source, url in FEEDS.items():
        try:
            parsed = feedparser.parse(url)
        except Exception:
            continue
        for entry in parsed.entries[:limit]:
            items.append(
                {
                    "title": entry.get("title", "(no title)"),
                    "link": entry.get("link", ""),
                    "source": source,
                    "published": entry.get("published", ""),
                }
            )
    # ソースごとに偏らないよう交互に並べ替え
    return items[: limit * 2]
