"""世界の経済ニュース取得モジュール。

無料の RSS フィードからヘッドラインを取得する。APIキー不要。
- 日本語の経済・国際フィード（NHK・Yahoo!ニュース）
- 米国 Yahoo Finance の S&P500 関連フィード（英語）
取得後、金利・株価に関連する見出しだけに絞り込んで返す。
取得できない場合は空リストを返し、UI 側で握りつぶす。
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request

import feedparser

# 日本語（ひらがな・カタカナ・漢字）が含まれるか判定する正規表現
_JP_RE = re.compile(r"[぀-ヿ一-鿿]")


def _has_japanese(text: str) -> bool:
    return bool(_JP_RE.search(text or ""))


def _t_mymemory(text: str) -> str:
    """MyMemory 翻訳API（無料・キー不要）。失敗時は空文字。"""
    try:
        params = urllib.parse.urlencode({"q": text, "langpair": "en|ja"})
        req = urllib.request.Request(
            f"https://api.mymemory.translated.net/get?{params}",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("responseData", {}).get("translatedText", "") or ""
    except Exception:
        return ""


def _t_google(text: str) -> str:
    """Google 翻訳の無料エンドポイント。クラウドでは弾かれることがある。"""
    try:
        params = urllib.parse.urlencode(
            {"client": "gtx", "sl": "en", "tl": "ja", "dt": "t", "q": text}
        )
        req = urllib.request.Request(
            f"https://translate.googleapis.com/translate_a/single?{params}",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        segments = data[0] or []
        return "".join(seg[0] for seg in segments if seg and seg[0])
    except Exception:
        return ""


def _t_deepl(text: str, key: str) -> str:
    """DeepL API（無料/有料）。キー末尾 :fx は無料版エンドポイントを使う。"""
    if not key:
        return ""
    try:
        host = "https://api-free.deepl.com" if key.endswith(":fx") else "https://api.deepl.com"
        body = urllib.parse.urlencode(
            {"text": text, "target_lang": "JA", "source_lang": "EN"}
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{host}/v2/translate",
            data=body,
            headers={
                "Authorization": f"DeepL-Auth-Key {key}",
                "User-Agent": "Mozilla/5.0",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["translations"][0]["text"]
    except Exception:
        return ""


def translate_to_ja(text: str, deepl_key: str | None = None) -> str:
    """英語見出しを日本語へ翻訳。DeepL→MyMemory→Google の順に試し、
    日本語が得られなければ原文をそのまま返す。"""
    if not text or _has_japanese(text):
        return text
    if deepl_key:
        out = _t_deepl(text, deepl_key)
        if out and _has_japanese(out):
            return out
    for fn in (_t_mymemory, _t_google):
        out = fn(text)
        if out and _has_japanese(out):
            return out
    return text

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


def fetch_news(limit: int = 12, deepl_key: str | None = None) -> list[dict]:
    """各フィードからヘッドラインを集約し、金利・株価関連だけ返す。

    deepl_key を渡すと英語見出しの日本語訳に DeepL を優先利用する。
    戻り値: [{"title", "title_ja", "link", "source", "published"}...]
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
            # 英語見出し（日本語を含まない）は日本語訳を併記用に付与
            title_ja = title if _has_japanese(title) else translate_to_ja(title, deepl_key)
            items.append(
                {
                    "title": title or "(no title)",
                    "title_ja": title_ja or title,
                    "link": entry.get("link", ""),
                    "source": source,
                    "published": entry.get("published", ""),
                }
            )
    return items
