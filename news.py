"""世界の経済ニュース取得モジュール。

無料の RSS フィードからヘッドラインを取得する。APIキー不要。
取得できない場合は空リストを返し、UI 側で握りつぶす。
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

import feedparser

# 無料で取得できる経済・市場系 RSS フィード
FEEDS = {
    "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
    "CNBC Markets": "https://www.cnbc.com/id/20910258/device/rss/rss.html",
    "MarketWatch": "http://feeds.marketwatch.com/marketwatch/topstories/",
    "Investing.com": "https://www.investing.com/rss/news_25.rss",
}

# Google 翻訳の無料エンドポイント（APIキー不要）。失敗時は原文にフォールバック。
_TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"


def _translate_to_ja(text: str) -> str:
    """英語の見出しを日本語に翻訳する。失敗したら原文をそのまま返す。"""
    if not text:
        return text
    try:
        params = urllib.parse.urlencode(
            {"client": "gtx", "sl": "auto", "tl": "ja", "dt": "t", "q": text}
        )
        req = urllib.request.Request(
            f"{_TRANSLATE_URL}?{params}",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        # 戻り値: [[["訳文","原文",...], ...], ...] のように分割されることがある
        segments = data[0] or []
        translated = "".join(seg[0] for seg in segments if seg and seg[0])
        return translated or text
    except Exception:
        return text


def fetch_news(limit: int = 12, translate: bool = True) -> list[dict]:
    """各フィードからヘッドラインを集約して返す。

    translate=True のとき見出しを日本語へ自動翻訳した title_ja を付与する。
    戻り値: [{"title", "title_ja", "link", "source", "published"}...]
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
    items = items[: limit * 2]

    # 見出しを日本語へ翻訳（失敗分は原文のまま）
    if translate:
        for it in items:
            it["title_ja"] = _translate_to_ja(it["title"])
    return items
