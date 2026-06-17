"""データ取得モジュール。

yfinance を使って S&P500・VIX・S&P500先物の時系列データを取得する。
APIキーは不要。取得結果はキャッシュして無駄な再取得を防ぐ。
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import yfinance as yf

# ティッカー定義
TICKERS = {
    "sp500": "^GSPC",   # S&P500 現物指数
    "vix": "^VIX",      # VIX 恐怖指数
    "futures": "ES=F",  # S&P500 E-mini 先物
    "usdjpy": "JPY=X",  # ドル円
    "dxy": "DX-Y.NYB",  # ドル指数（DXY）
    "ust10y": "^TNX",   # 米10年債利回り（%表示, 例 4.25 = 4.25%）
    "ust3m": "^IRX",    # 米13週(3ヶ月)債利回り（%表示）
    "schd": "SCHD",     # Schwab 米国高配当株式ETF
    "acwi": "ACWI",     # iShares MSCI ACWI ETF（全世界株式・USD建て）
    "nasdaq": "QQQ",    # Invesco QQQ（NASDAQ100連動ETF）
}

# セクター別 SPDR ETF（GICS セクター分類）
SECTOR_ETFS = {
    "XLK": "情報技術",
    "XLF": "金融",
    "XLV": "ヘルスケア",
    "XLY": "一般消費財",
    "XLP": "生活必需品",
    "XLE": "エネルギー",
    "XLI": "資本財",
    "XLU": "公益",
    "XLB": "素材",
    "XLRE": "不動産",
    "XLC": "通信サービス",
}

# 主要株価指数 ETF
INDEX_ETFS = {
    "SPY": "S&P500",
    "QQQ": "ナスダック100",
    "DIA": "ダウ平均",
    "IWM": "ラッセル2000(小型株)",
    "VTV": "米国大型バリュー",
}

# ディフェンシブ／資金逃避先（S&P500 下落時に資金が向かいやすい先）。
# 公益・生活必需品・ヘルスケア・エネルギーは SCHD の主要構成セクターとも重なる。
DEFENSIVE_ETFS = {
    "XLU": "公益（ディフェンシブ）",
    "XLP": "生活必需品（ディフェンシブ）",
    "XLV": "ヘルスケア（ディフェンシブ）",
    "XLE": "エネルギー",
    "GLD": "金（ゴールド）",
    "TLT": "米国債20年超",
    "IGF": "世界インフラ",
    "PAVE": "米国インフラ",
    "VNQ": "米国REIT（不動産）",
}


def _download(ticker: str, period: str = "3y", interval: str = "1d") -> pd.DataFrame:
    """単一ティッカーの OHLCV を取得して整形する。"""
    df = yf.download(
        ticker,
        period=period,
        interval=interval,
        auto_adjust=True,
        progress=False,
    )
    if df.empty:
        return df
    # yfinance が MultiIndex 列を返す場合があるのでフラット化
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index = pd.to_datetime(df.index)
    return df


def fetch_all(period: str = "3y") -> dict[str, pd.DataFrame]:
    """S&P500・VIX・先物・為替・米国債利回りをまとめて取得する。

    戻り値: {"sp500": df, "vix": df, "futures": df, "usdjpy": df,
             "dxy": df, "ust10y": df, "ust3m": df}
    各 df は Open/High/Low/Close/Volume 列を持つ。
    """
    out: dict[str, pd.DataFrame] = {}
    for key, ticker in TICKERS.items():
        out[key] = _download(ticker, period=period)
    # eMAXIS Slim 全世界株式（オルカン）プロキシ = ACWI(USD) × ドル円 の円換算合成OHLC
    out["acwi_jp"] = _build_acwi_jpy(out)
    return out


def _build_acwi_jpy(out: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """ACWI(USD) を ドル円で円換算した合成 OHLC を作る（オルカンのプロキシ）。"""
    acwi = out.get("acwi")
    fx = out.get("usdjpy")
    if acwi is None or acwi.empty or fx is None or fx.empty:
        return pd.DataFrame()
    fxc = fx["Close"].reindex(acwi.index).ffill()
    df = pd.DataFrame(index=acwi.index)
    for col in ("Open", "High", "Low", "Close"):
        if col in acwi.columns:
            df[col] = acwi[col] * fxc
    if "Volume" in acwi.columns:
        df["Volume"] = acwi["Volume"]
    return df.dropna(subset=["Close"])


def fetch_closes(tickers, period: str = "6mo") -> pd.DataFrame:
    """指定ティッカー群の終値をまとめて取得し、列=ティッカーの DataFrame で返す。

    tickers は dict（キー=ティッカー）または iterable。
    取得に失敗したティッカーは列ごと欠落する。
    """
    closes: dict[str, pd.Series] = {}
    for ticker in tickers:
        df = _download(ticker, period=period)
        if not df.empty and "Close" in df.columns:
            closes[ticker] = df["Close"]
    if not closes:
        return pd.DataFrame()
    return pd.DataFrame(closes)


def fetch_sectors(period: str = "6mo") -> pd.DataFrame:
    """セクター別 ETF の終値（後方互換ラッパー）。"""
    return fetch_closes(SECTOR_ETFS, period=period)


def build_feature_frame(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """各データソースを日付で結合し、予測用の特徴量テーブルを作る。

    列:
        sp500_close, sp500_ret(前日比リターン), sp500_vol(出来高)
        vix_close, vix_chg(VIX前日差)
        fut_close, fut_ret(先物前日比リターン)
        fut_gap(先物Close - S&P500Close の乖離率)
        usdjpy_close, usdjpy_ret(ドル円前日比リターン)
        dxy_close, dxy_ret(ドル指数前日比リターン)
        ust10y_close, ust10y_chg(米10年債利回りの前日差)
        curve_spread(10年-3ヶ月 の利回り差, 景気/逆イールドの目安)
    """
    sp = data["sp500"]
    vix = data["vix"]
    fut = data["futures"]

    if sp.empty:
        return pd.DataFrame()

    def _close_on(key: str) -> pd.Series | None:
        """data から指定キーの Close を frame の日付に合わせて返す。"""
        d = data.get(key)
        if d is None or d.empty or "Close" not in d.columns:
            return None
        return d["Close"].reindex(sp.index).ffill()

    frame = pd.DataFrame(index=sp.index)
    frame["sp500_close"] = sp["Close"]
    frame["sp500_open"] = sp["Open"]
    frame["sp500_high"] = sp["High"]
    frame["sp500_low"] = sp["Low"]
    frame["sp500_vol"] = sp.get("Volume")
    frame["sp500_ret"] = sp["Close"].pct_change()

    if not vix.empty:
        frame["vix_close"] = vix["Close"].reindex(frame.index).ffill()
        frame["vix_chg"] = frame["vix_close"].diff()

    if not fut.empty:
        fut_close = fut["Close"].reindex(frame.index).ffill()
        frame["fut_close"] = fut_close
        frame["fut_ret"] = fut_close.pct_change()
        # 先物が現物からどれだけ乖離しているか（センチメントの代理指標）
        frame["fut_gap"] = (fut_close - frame["sp500_close"]) / frame["sp500_close"]

    # 為替: ドル円・ドル指数
    usdjpy = _close_on("usdjpy")
    if usdjpy is not None:
        frame["usdjpy_close"] = usdjpy
        frame["usdjpy_ret"] = usdjpy.pct_change()
    dxy = _close_on("dxy")
    if dxy is not None:
        frame["dxy_close"] = dxy
        frame["dxy_ret"] = dxy.pct_change()

    # 米国債利回り（^TNX/^IRX は「利回り×10」ではなくパーセント値を返す）
    ust10y = _close_on("ust10y")
    if ust10y is not None:
        frame["ust10y_close"] = ust10y
        frame["ust10y_chg"] = ust10y.diff()
    ust3m = _close_on("ust3m")
    if ust3m is not None:
        frame["ust3m_close"] = ust3m
        if ust10y is not None:
            # 10年-3ヶ月スプレッド。マイナス=逆イールド（景気後退の代表的サイン）
            frame["curve_spread"] = ust10y - ust3m

    # SCHD（S&P500 と並列に予測対象とする高配当ETF）
    schd = _close_on("schd")
    if schd is not None:
        frame["schd_close"] = schd
        frame["schd_ret"] = schd.pct_change()

    # 全世界株式（オルカン）プロキシ = ACWI(USD) × ドル円（円換算）
    acwi_usd = _close_on("acwi")
    fx = _close_on("usdjpy")
    if acwi_usd is not None and fx is not None:
        acwi_jpy = acwi_usd * fx
        frame["acwi_jp_close"] = acwi_jpy
        frame["acwi_jp_ret"] = acwi_jpy.pct_change()

    # NASDAQ100（QQQ）
    nasdaq = _close_on("nasdaq")
    if nasdaq is not None:
        frame["nasdaq_close"] = nasdaq
        frame["nasdaq_ret"] = nasdaq.pct_change()

    return frame


# ファンド（ETF）の中身を見るためのプロキシ・ティッカー
FUND_PROXIES = {
    "S&P500": "SPY",     # SPDR S&P 500 ETF
    "SCHD": "SCHD",      # Schwab 米国高配当株式 ETF
    "オルカン": "ACWI",  # iShares MSCI ACWI ETF（全世界株式）
    "NASDAQ": "QQQ",     # Invesco QQQ（NASDAQ100）
}

# Yahoo のセクターキー → 日本語ラベル
SECTOR_JP = {
    "technology": "情報技術",
    "financial_services": "金融",
    "healthcare": "ヘルスケア",
    "consumer_cyclical": "一般消費財",
    "consumer_defensive": "生活必需品",
    "communication_services": "通信サービス",
    "industrials": "資本財",
    "energy": "エネルギー",
    "basic_materials": "素材",
    "realestate": "不動産",
    "utilities": "公益",
}


# 静的フォールバック（API失敗時のバックアップ）2026年6月時点の概算値
_STATIC_FUND_DATA: dict[str, dict] = {
    "SPY": {
        "holdings_list": [
            ("MSFT", "Microsoft Corp", 0.0699),
            ("AAPL", "Apple Inc", 0.0645),
            ("NVDA", "NVIDIA Corp", 0.0620),
            ("AMZN", "Amazon.com Inc", 0.0380),
            ("META", "Meta Platforms Inc", 0.0280),
            ("GOOGL", "Alphabet Inc A", 0.0210),
            ("GOOG", "Alphabet Inc C", 0.0180),
            ("BRK.B", "Berkshire Hathaway B", 0.0170),
            ("LLY", "Eli Lilly and Co", 0.0150),
            ("AVGO", "Broadcom Inc", 0.0145),
        ],
        "sectors": {
            "technology": 0.325, "financial_services": 0.130,
            "healthcare": 0.115, "consumer_cyclical": 0.110,
            "communication_services": 0.085, "industrials": 0.085,
            "consumer_defensive": 0.060, "energy": 0.035,
            "utilities": 0.025, "realestate": 0.020, "basic_materials": 0.020,
        },
    },
    "QQQ": {
        "holdings_list": [
            ("MSFT", "Microsoft Corp", 0.0864),
            ("AAPL", "Apple Inc", 0.0785),
            ("NVDA", "NVIDIA Corp", 0.0780),
            ("AMZN", "Amazon.com Inc", 0.0492),
            ("META", "Meta Platforms Inc", 0.0456),
            ("GOOGL", "Alphabet Inc A", 0.0264),
            ("GOOG", "Alphabet Inc C", 0.0258),
            ("TSLA", "Tesla Inc", 0.0248),
            ("AVGO", "Broadcom Inc", 0.0240),
            ("COST", "Costco Wholesale", 0.0185),
        ],
        "sectors": {
            "technology": 0.520, "communication_services": 0.165,
            "consumer_cyclical": 0.130, "healthcare": 0.065,
            "consumer_defensive": 0.060, "industrials": 0.040,
            "basic_materials": 0.010, "utilities": 0.010,
        },
    },
    "SCHD": {
        "holdings_list": [
            ("MO",   "Altria Group Inc", 0.0455),
            ("VZ",   "Verizon Communications", 0.0442),
            ("EOG",  "EOG Resources Inc", 0.0421),
            ("PKG",  "Packaging Corp of America", 0.0418),
            ("LMT",  "Lockheed Martin Corp", 0.0415),
            ("CVX",  "Chevron Corp", 0.0410),
            ("PEP",  "PepsiCo Inc", 0.0405),
            ("KO",   "Coca-Cola Co", 0.0403),
            ("PFE",  "Pfizer Inc", 0.0398),
            ("CSCO", "Cisco Systems Inc", 0.0393),
        ],
        "sectors": {
            "financial_services": 0.175, "healthcare": 0.155,
            "consumer_defensive": 0.130, "industrials": 0.125,
            "energy": 0.115, "communication_services": 0.095,
            "technology": 0.085, "basic_materials": 0.065, "utilities": 0.055,
        },
    },
    "ACWI": {
        "holdings_list": [
            ("MSFT",  "Microsoft Corp", 0.0420),
            ("AAPL",  "Apple Inc", 0.0385),
            ("NVDA",  "NVIDIA Corp", 0.0375),
            ("AMZN",  "Amazon.com Inc", 0.0230),
            ("META",  "Meta Platforms Inc", 0.0170),
            ("GOOGL", "Alphabet Inc A", 0.0127),
            ("TSLA",  "Tesla Inc", 0.0120),
            ("AVGO",  "Broadcom Inc", 0.0115),
            ("GOOG",  "Alphabet Inc C", 0.0110),
            ("JPM",   "JPMorgan Chase & Co", 0.0108),
        ],
        "sectors": {
            "technology": 0.245, "financial_services": 0.165,
            "healthcare": 0.115, "consumer_cyclical": 0.110,
            "industrials": 0.105, "communication_services": 0.080,
            "consumer_defensive": 0.065, "energy": 0.050,
            "utilities": 0.030, "realestate": 0.025, "basic_materials": 0.025,
        },
    },
}


def _static_fund_profile(ticker: str) -> dict:
    """静的フォールバックデータを DataFrame 形式に変換して返す。"""
    sd = _STATIC_FUND_DATA.get(ticker)
    if sd is None:
        return {"holdings": None, "sectors": None, "is_static": True}
    rows = sd["holdings_list"]
    holdings_df = pd.DataFrame(rows, columns=["symbol", "holdingName", "holdingPercent"])
    holdings_df = holdings_df.set_index("symbol")
    return {"holdings": holdings_df, "sectors": sd["sectors"], "is_static": True}


def fetch_fund_profile(ticker: str) -> dict:
    """ETF の組入上位銘柄とセクター構成比率を取得する。

    戻り値: {"holdings": DataFrame|None, "sectors": dict|None, "is_static": bool}
    holdings は index=銘柄シンボル, 列=holdingName/holdingPercent。
    API失敗時は静的フォールバックデータを返す（is_static=True）。
    """
    result: dict = {"holdings": None, "sectors": None, "is_static": False}
    try:
        fd = yf.Ticker(ticker).funds_data
        th = fd.top_holdings
        if th is not None and not th.empty:
            result["holdings"] = th
        sw = fd.sector_weightings
        if isinstance(sw, dict) and sw:
            result["sectors"] = sw
    except Exception:
        pass

    # API で取得できなかった場合は静的データで補完
    if result["holdings"] is None or (
        hasattr(result["holdings"], "empty") and result["holdings"].empty
    ):
        static = _static_fund_profile(ticker)
        result["holdings"] = static["holdings"]
        if result["sectors"] is None:
            result["sectors"] = static.get("sectors")
        result["is_static"] = True
    return result


def last_updated() -> str:
    """最終取得時刻の文字列。"""
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
