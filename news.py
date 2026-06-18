"""世界の経済ニュース取得モジュール。

無料の RSS フィードからヘッドラインを取得する。APIキー不要。
- 日本語の経済・国際フィード（NHK・Yahoo!ニュース）
- 米国 Yahoo Finance の S&P500 関連フィード（英語）
取得後、金利・株価に関連する見出しだけに絞り込んで返す。
取得できない場合は空リストを返し、UI 側で握りつぶす。
"""
from __future__ import annotations

import feedparser

# 日本語の経済・国際ニュース RSS フィード
FEEDS_JP = {
    "NHK ビジネス": "https://www.nhk.or.jp/rss/news/cat5.xml",
    "Yahoo!ニュース 経済": "https://news.yahoo.co.jp/rss/categories/business.xml",
    "Yahoo!ニュース 国際": "https://news.yahoo.co.jp/rss/categories/world.xml",
}

# 米国 Yahoo Finance の S&P500 銘柄ニュース（英語）
FEEDS_US = {
    "米国 Yahoo Finance (S&P500)": (
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=%5EGSPC&region=US&lang=en-US"
    ),
}

# 金利・株価に関連する見出しだけ残すためのキーワード（日本語）。
# 「株」単体や「上場」は株主総会・上場来などノイズを拾うため入れない。
_KEYWORDS_JA = [
    "金利", "利上げ", "利下げ", "利回り", "国債", "債券",
    "株価", "株式", "日経", "ダウ", "ナスダック", "S&P", "S＆P",
    "FRB", "FOMC", "中央銀行", "日銀",
    "為替", "円相場", "円安", "円高", "ドル",
    "相場", "インフレ", "物価",
]
# 同（英語・小文字で照合）
_KEYWORDS_EN = [
    "rate", "rates", "fed", "fomc", "yield", "treasury", "bond",
    "stock", "stocks", "market", "markets", "s&p", "nasdaq", "dow",
    "equit", "share", "shares", "rally", "dividend", "earnings",
    "inflation", "cpi", "jobless", "wall street", "index", "futures",
]


def _is_relevant(title: str) -> bool:
    """見出しが金利・株価に関連していれば True。"""
    if not title:
        return False
    low = title.lower()
    if any(kw in title for kw in _KEYWORDS_JA):
        return True
    if any(kw in low for kw in _KEYWORDS_EN):
        return True
    return False


def fetch_news(limit: int = 12) -> list[dict]:
    """各フィードからヘッドラインを集約し、金利・株価関連だけ返す。

    戻り値: [{"title", "link", "source", "published"}...]
    """
    items: list[dict] = []
    feeds = {**FEEDS_JP, **FEEDS_US}
    for source, url in feeds.items():
        try:
            parsed = feedparser.parse(url)
        except Exception:
            continue
        for entry in parsed.entries[:limit]:
            title = entry.get("title", "")
            if not _is_relevant(title):
                continue
            items.append(
                {
                    "title": title or "(no title)",
                    "link": entry.get("link", ""),
                    "source": source,
                    "published": entry.get("published", ""),
                }
            )
    return items
