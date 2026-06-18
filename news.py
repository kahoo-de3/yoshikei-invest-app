"""世界の経済ニュース取得モジュール。

無料の日本語 RSS フィードからヘッドラインを取得する。APIキー不要。
（海外英語フィードを翻訳する方式はクラウド環境で翻訳APIが弾かれやすいため、
最初から日本語のニュースソースを使う方式に変更）
取得できない場合は空リストを返し、UI 側で握りつぶす。
"""
from __future__ import annotations

import feedparser

# 日本語の経済・国際ニュース RSS フィード（最初から日本語なので翻訳不要）
FEEDS = {
    "NHK ビジネス": "https://www.nhk.or.jp/rss/news/cat5.xml",
    "Yahoo!ニュース 経済": "https://news.yahoo.co.jp/rss/categories/business.xml",
    "Yahoo!ニュース 国際": "https://news.yahoo.co.jp/rss/categories/world.xml",
}


def fetch_news(limit: int = 8) -> list[dict]:
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
    return items
