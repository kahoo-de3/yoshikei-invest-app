"""S&P500 投資情報ダッシュボード（Streamlit）。

機能:
    - S&P500 の時系列チャート（毎日更新）
    - VIX 指数・S&P500 先物の現況
    - 世界の経済ニュースヘッドライン
    - 翌日の予測値（参考シグナル）

起動方法:
    streamlit run app.py

注意: 本アプリの予測は参考情報であり、投資成果を保証しません。
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

import data as data_mod
import model as model_mod
import news as news_mod

st.set_page_config(
    page_title="FIREを目指そう by よしけい",
    layout="wide", page_icon="🪙",
    initial_sidebar_state="collapsed",  # スマホで本文を広く使う
)

# スマホ向け: ツールバー（ズーム＋リセット）を表示しつつ、2本指ピンチも有効化。
# ピンチで空白になっても「⌂ 軸をリセット」ボタンで一発で元に戻せる。
MOBILE_CONFIG = {
    "displayModeBar": True,
    "displaylogo": False,
    "responsive": True,
    "scrollZoom": True,
    "modeBarButtonsToRemove": ["select2d", "lasso2d", "toImage"],
}

# 各チャートの上に表示する操作説明（PC・スマホ共通）
CHART_OP_HELP = (
    "※ パソコン  \n"
    "ドラッグで範囲を囲んで拡大／ダブルクリックで戻る  \n"
    "※ モバイル  \n"
    "2本指ピンチで拡大・縮小／ダブルタップで戻る"
)


def section_title(text: str):
    """金文字の共通セクション見出し（中央揃え・「セクター構成比率」と同サイズ）。"""
    st.markdown(
        f"<div style='text-align:center; font-weight:700; color:#E9C766; "
        f"font-size:1.2rem; margin:0.3em 0;'>{text}</div>",
        unsafe_allow_html=True,
    )


def card_note(col, text: str):
    """メトリクスカードの直下に引用元の商品名を小さく常時表示する。"""
    col.markdown(
        f"<div style='text-align:center; font-size:0.66rem; color:#bdb7a8; "
        f"margin-top:-8px; margin-bottom:6px;'>{text}</div>",
        unsafe_allow_html=True,
    )


# 業種ごとの固定色（英語キー基準で、全ファンドの業種構成比率の色を統一）
# データ元(ライブAPI/静的)で日本語ラベルがズレても英語キーは共通なので確実。
SECTOR_COLORS = {
    "technology": "#E6194B",           # 情報技術 ・赤
    "financial_services": "#F58231",   # 金融 ・橙
    "healthcare": "#FFE119",           # ヘルスケア ・黄
    "consumer_cyclical": "#BFEF45",    # 一般消費財 ・黄緑
    "communication_services": "#3CB44B",  # 通信サービス ・緑
    "industrials": "#42D4F4",          # 資本財 ・水色
    "consumer_defensive": "#4363D8",   # 生活必需品 ・青
    "energy": "#911EB4",               # エネルギー ・紫
    "utilities": "#F032E6",            # 公益 ・マゼンタ
    "realestate": "#A9A9A9",           # 不動産 ・灰
    "basic_materials": "#9A6324",      # 素材 ・茶
}

# 組入上位銘柄（主要ティッカー）→ 業種キー。表の行を業種色で塗るのに使う。
STOCK_SECTOR = {
    # 情報技術
    "MSFT": "technology", "AAPL": "technology", "NVDA": "technology",
    "AVGO": "technology", "CSCO": "technology", "AMD": "technology",
    "MU": "technology", "INTC": "technology", "QCOM": "technology",
    "TXN": "technology", "ORCL": "technology", "CRM": "technology",
    "ADBE": "technology", "ACN": "technology", "IBM": "technology",
    "NOW": "technology", "INTU": "technology", "AMAT": "technology",
    "LRCX": "technology", "ADI": "technology", "KLAC": "technology",
    "PLTR": "technology", "PANW": "technology", "ANET": "technology",
    "CDNS": "technology", "SNPS": "technology", "MRVL": "technology",
    "APH": "technology", "MSI": "technology",
    # 通信サービス
    "META": "communication_services", "GOOGL": "communication_services",
    "GOOG": "communication_services", "VZ": "communication_services",
    "NFLX": "communication_services", "CMCSA": "communication_services",
    "DIS": "communication_services", "T": "communication_services",
    "TMUS": "communication_services",
    # 一般消費財
    "AMZN": "consumer_cyclical", "TSLA": "consumer_cyclical",
    "HD": "consumer_cyclical", "MCD": "consumer_cyclical",
    "NKE": "consumer_cyclical", "SBUX": "consumer_cyclical",
    "LOW": "consumer_cyclical", "BKNG": "consumer_cyclical",
    "TJX": "consumer_cyclical", "ABNB": "consumer_cyclical",
    # 生活必需品
    "COST": "consumer_defensive", "MO": "consumer_defensive",
    "PEP": "consumer_defensive", "KO": "consumer_defensive",
    "WMT": "consumer_defensive", "PG": "consumer_defensive",
    "PM": "consumer_defensive", "MDLZ": "consumer_defensive",
    "CL": "consumer_defensive",
    # 金融
    "BRK.B": "financial_services", "JPM": "financial_services",
    "V": "financial_services", "MA": "financial_services",
    "BAC": "financial_services", "WFC": "financial_services",
    "GS": "financial_services", "MS": "financial_services",
    "AXP": "financial_services", "BLK": "financial_services",
    "SPGI": "financial_services", "C": "financial_services",
    # ヘルスケア
    "LLY": "healthcare", "PFE": "healthcare", "UNH": "healthcare",
    "JNJ": "healthcare", "ABBV": "healthcare", "MRK": "healthcare",
    "TMO": "healthcare", "ABT": "healthcare", "DHR": "healthcare",
    "AMGN": "healthcare", "BMY": "healthcare", "GILD": "healthcare",
    # 資本財
    "LMT": "industrials", "CAT": "industrials", "BA": "industrials",
    "HON": "industrials", "GE": "industrials", "RTX": "industrials",
    "UPS": "industrials", "UNP": "industrials", "DE": "industrials",
    "ETN": "industrials", "EMR": "industrials",
    # エネルギー
    "EOG": "energy", "CVX": "energy", "XOM": "energy", "COP": "energy",
    "SLB": "energy", "PSX": "energy", "MPC": "energy", "OXY": "energy",
    "WMB": "energy",
    # 素材
    "PKG": "basic_materials", "LIN": "basic_materials",
    "SHW": "basic_materials", "APD": "basic_materials",
    "FCX": "basic_materials", "NEM": "basic_materials",
    "ECL": "basic_materials",
    # 公益
    "NEE": "utilities", "DUK": "utilities", "SO": "utilities",
    "D": "utilities", "AEP": "utilities",
    # 不動産
    "PLD": "realestate", "AMT": "realestate", "EQIX": "realestate",
    "O": "realestate", "SPG": "realestate",
}


# セクターETFティッカー → 業種色（業種構成比率と同じ配色で統一）
SECTOR_ETF_COLORS = {
    "XLK": SECTOR_COLORS["technology"],
    "XLF": SECTOR_COLORS["financial_services"],
    "XLV": SECTOR_COLORS["healthcare"],
    "XLY": SECTOR_COLORS["consumer_cyclical"],
    "XLP": SECTOR_COLORS["consumer_defensive"],
    "XLE": SECTOR_COLORS["energy"],
    "XLI": SECTOR_COLORS["industrials"],
    "XLU": SECTOR_COLORS["utilities"],
    "XLB": SECTOR_COLORS["basic_materials"],
    "XLRE": SECTOR_COLORS["realestate"],
    "XLC": SECTOR_COLORS["communication_services"],
}

# 資金逃避先ETF → 業種色（対応する業種があるものだけ。無いものは未着色＝黒のまま）
DEFENSIVE_ETF_COLORS = {
    "XLU": SECTOR_COLORS["utilities"],          # 公益
    "XLP": SECTOR_COLORS["consumer_defensive"], # 生活必需品
    "XLV": SECTOR_COLORS["healthcare"],         # ヘルスケア
    "XLE": SECTOR_COLORS["energy"],             # エネルギー
    "VNQ": SECTOR_COLORS["realestate"],         # 不動産（REIT）
    "GLD": ("#ffffff", "#d62828"),              # 金 → 白地に赤
    "TLT": ("#ffffff", "#1f5fd8"),              # 米国債20年 → 白地に青
    # IGF/PAVE(インフラ) は対応色なし → 黒のまま
}


def _text_on(hexc: str) -> str:
    """背景色の明るさに応じて、読みやすい文字色(黒/白)を返す。"""
    h = hexc.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    return "#000000" if lum > 150 else "#ffffff"

# ---- チャートだけライト配色にする共通テンプレート ----
# 背景ダーク × チャートはライトで見やすく。縦軸・横軸に目盛りとグリッドを表示。
pio.templates["light_chart"] = go.layout.Template(
    layout=dict(
        paper_bgcolor="#f7f5ee",
        plot_bgcolor="#ffffff",
        font=dict(color="#222222", family="'Noto Sans JP', sans-serif"),
        title=dict(font=dict(color="#333333", family="'Noto Sans JP', sans-serif")),
        legend=dict(font=dict(color="#333333", family="'Noto Sans JP', sans-serif")),
        xaxis=dict(
            gridcolor="#e4e1d7", linecolor="#c9c4b5", zerolinecolor="#e4e1d7",
            ticks="outside", tickcolor="#c9c4b5", showgrid=True,
        ),
        yaxis=dict(
            gridcolor="#e4e1d7", linecolor="#c9c4b5", zerolinecolor="#e4e1d7",
            ticks="outside", tickcolor="#c9c4b5", showgrid=True,
        ),
    )
)
pio.templates.default = "light_chart"


def monthly_axis(fig):
    """時系列チャートの横軸を月単位の目盛り・グリッドにする。

    縦軸の目盛り・グリッドは light_chart テンプレート側で全チャート共通に付与。
    """
    fig.update_xaxes(
        dtick="M1", tickformat="%Y/%m", tickangle=-45,
        ticklabelmode="period", automargin=True, tickfont=dict(size=9),
        gridcolor="#e4e1d7", linecolor="#c9c4b5", tickcolor="#c9c4b5",
    )
    fig.update_yaxes(
        automargin=True, showgrid=True, tickfont=dict(size=10),
        gridcolor="#e4e1d7", linecolor="#c9c4b5", tickcolor="#c9c4b5",
    )
    return fig


# ---- 外観: ダーク基調 + 金貨を散りばめたテーマ ----
def inject_theme():
    """ダーク背景・ゴールドのアクセント・背景に散らした金貨を CSS で適用。"""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=swap');

        /* フォント統一: Streamlit UI 全体 */
        html, body, [class*="css"], .stApp, .stMarkdown, .stDataFrame,
        div[data-testid="stMetricValue"], div[data-testid="stMetricLabel"],
        button, input, select, textarea {
            font-family: 'Noto Sans JP', sans-serif !important;
        }

        /* 全体の背景: 灰色 + ほのかな金色グロー */
        .stApp {
            background:
                radial-gradient(1100px 600px at 12% -8%, rgba(212,175,55,0.08), transparent 60%),
                radial-gradient(900px 500px at 92% 8%, rgba(212,175,55,0.05), transparent 60%),
                linear-gradient(160deg, #5a5e63 0%, #4c5055 55%, #43464b 100%);
        }

        /* 背景に散りばめた金貨（最背面・操作の邪魔をしない） */
        .coin-layer {
            position: fixed;
            inset: 0;
            pointer-events: none;
            z-index: 0;
            overflow: hidden;
        }
        .coin-layer span {
            position: absolute;
            font-size: 3.2rem;
            opacity: 0.25;
            filter: drop-shadow(0 0 10px rgba(212,175,55,0.42));
        }

        /* 見出しをゴールドに・中央揃え */
        h1, h2, h3 { color: #E9C766 !important; letter-spacing: .02em; text-align: center; }

        /* メトリクスカードを金縁のガラス風に */
        div[data-testid="stMetric"] {
            background: rgba(23,26,34,0.72);
            border: 1px solid rgba(212,175,55,0.35);
            border-radius: 14px;
            padding: 14px 16px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.45),
                        inset 0 0 0 1px rgba(212,175,55,0.06);
            backdrop-filter: blur(3px);
        }
        div[data-testid="stMetricValue"] { color: #F2E2A8 !important; }

        /* メトリクスカードの中身（ラベル・数値・前日比）を中央揃え */
        div[data-testid="stMetric"] { text-align: center !important; }
        div[data-testid="stMetric"] label,
        div[data-testid="stMetricLabel"],
        div[data-testid="stMetricLabel"] > div,
        div[data-testid="stMetricValue"],
        div[data-testid="stMetricValue"] > div,
        div[data-testid="stMetricDelta"] {
            display: flex !important;
            justify-content: center !important;
            text-align: center !important;
            width: 100% !important;
        }

        /* 展開メニュー（expander）の見出しを枠内中央揃え */
        details[data-testid="stExpander"] summary {
            justify-content: center !important;
        }
        details[data-testid="stExpander"] summary p {
            text-align: center !important;
            width: 100%;
        }

        /* サイドバー */
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #42454a 0%, #393c41 100%);
            border-right: 1px solid rgba(212,175,55,0.20);
        }

        /* 区切り線をゴールドのグラデに */
        hr {
            border: none;
            height: 1px;
            background: linear-gradient(90deg, transparent, rgba(212,175,55,0.55), transparent);
        }

        /* 本文が金貨の上に来るように */
        .block-container { position: relative; z-index: 1; }

        /* チャート上の2本指ピンチをブラウザに横取りさせずPlotlyへ渡す */
        [data-testid="stPlotlyChart"],
        [data-testid="stPlotlyChart"] .js-plotly-plot,
        [data-testid="stPlotlyChart"] .plot-container,
        [data-testid="stPlotlyChart"] .nsewdrag {
            touch-action: none !important;
        }

        /* ===== スマートフォン最適化（横幅640px以下） ===== */
        @media (max-width: 640px) {
            .block-container {
                padding: 0.6rem 0.7rem 2.5rem 0.7rem !important;
            }
            h1 { font-size: 1.35rem !important; line-height: 1.3; }
            h2 { font-size: 1.1rem !important; }
            h3 { font-size: 0.98rem !important; }
            /* メトリクスカードを小さく詰める */
            div[data-testid="stMetric"] { padding: 8px 10px; }
            div[data-testid="stMetricValue"] { font-size: 1.15rem !important; }
            div[data-testid="stMetricLabel"] p { font-size: 0.7rem !important; }
            /* タブ見出しを折り返さず小さく */
            button[data-baseweb="tab"] { padding: 6px 8px !important; }
            button[data-baseweb="tab"] p { font-size: 0.8rem !important; }
            /* 背景コインは小さめに */
            .coin-layer span { font-size: 2rem !important; }
        }
        </style>

        <div class="coin-layer">
            <span style="top:7%;  left:3%;">💵</span>
            <span style="top:20%; left:90%;">💵</span>
            <span style="top:38%; left:12%;">💵</span>
            <span style="top:54%; left:84%;">💵</span>
            <span style="top:70%; left:28%;">💵</span>
            <span style="top:84%; left:64%;">💵</span>
            <span style="top:12%; left:52%;">💵</span>
            <span style="top:46%; left:44%;">💵</span>
            <span style="top:90%; left:8%;">💵</span>
            <span style="top:30%; left:70%;">💵</span>
            <span style="top:62%; left:4%;">💵</span>
            <span style="top:4%;  left:76%;">💵</span>
            <span style="top:77%; left:46%;">💵</span>
            <span style="top:26%; left:30%;">💵</span>
            <span style="top:58%; left:60%;">💵</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


inject_theme()


# ---- データ取得（1時間キャッシュ。手動更新ボタンあり）----
@st.cache_data(ttl=900, show_spinner="市場データを取得中...")  # 15分
def load_data(period: str):
    raw = data_mod.fetch_all(period=period)
    frame = data_mod.build_feature_frame(raw)
    # 取得時刻（キャッシュ生成時）を日本時間で記録
    fetched_at = pd.Timestamp.now(tz="Asia/Tokyo").strftime("%Y/%m/%d %H:%M")
    return raw, frame, fetched_at


@st.cache_data(ttl=3600, show_spinner="日本国債データを取得中...")  # 1時間
def load_jgb():
    return data_mod.fetch_jgb_yields()


@st.cache_data(ttl=900, show_spinner="セクターETFを取得中...")  # 15分
def load_sectors(period: str):
    return data_mod.fetch_sectors(period=period)


@st.cache_data(ttl=900, show_spinner="ETFデータを取得中...")  # 15分
def load_group(tickers: tuple, period: str):
    # tickers は tuple（キャッシュキーにできるよう）で受け取る
    return data_mod.fetch_closes(tickers, period=period)


@st.cache_data(ttl=86400, show_spinner="ファンド構成を取得中...")  # 1日
def load_fund_profile(ticker: str):
    return data_mod.fetch_fund_profile(ticker)


# ニュース取得ロジックを変えたらこの版数を上げる（キャッシュ強制無効化用）。
# Streamlit は load_news 自体の変化しか検知しないため、別モジュール側の
# 変更を確実に反映させるにはこの引数を変える必要がある。
_NEWS_VER = "2026-06-filter-us-bilingual"


@st.cache_data(ttl=300, show_spinner="ニュースを取得中...")  # 5分
def load_news(version: str = _NEWS_VER):
    return news_mod.fetch_news()


# ---- サイドバー ----
PERIOD_JP = {"6mo": "6ヶ月", "1y": "1年", "3y": "3年", "5y": "5年", "10y": "10年", "max": "全期間"}
_PERIOD_OPTIONS = ["6mo", "1y", "3y", "5y", "10y", "max"]
st.sidebar.title("⚙️ 設定")
period = st.sidebar.selectbox(
    "表示期間",
    options=_PERIOD_OPTIONS,
    index=_PERIOD_OPTIONS.index("10y"),  # デフォルト10年
    format_func=lambda x: PERIOD_JP[x],
)
# 表示期間に応じた騰落列名（例: 3年騰落 %）
PERIOD_COL = f"{PERIOD_JP[period]}騰落 %"
if st.sidebar.button("🔄 データを今すぐ更新"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.caption(f"最終取得: {data_mod.last_updated()}")
st.sidebar.markdown("---")
st.sidebar.caption(
    "⚠️ 予測値は過去データに基づく参考シグナルです。"
    "将来の値を保証するものではなく、投資は自己責任で行ってください。"
)

# ---- データロード ----
raw, frame, fetched_at = load_data(period)

st.markdown(
    """
    <div style="text-align:center; font-weight:700; color:#E9C766;
                font-size:1.8rem; line-height:1.2; margin:0;
                white-space:nowrap;">
        FIREを目指そう
    </div>
    <div style="text-align:center; font-weight:700; color:#E9C766;
                font-size:clamp(1.2rem, 4vw, 1.7rem); margin:0.15em 0 0.3em 0;">
        by よしけい
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    "<div style='text-align:center; font-size:0.85rem; color:#FFA500;'>"
    "※ 最下部まで読み込むのに数秒かかります。<br>"
    "キャラクターが動いているとloading中です。</div>",
    unsafe_allow_html=True,
)

if frame.empty:
    st.error("市場データを取得できませんでした。ネットワーク接続を確認して再度更新してください。")
    st.stop()

# ---- 現況メトリクス ----
latest = frame.dropna(subset=["sp500_close"]).iloc[-1]
prev = frame.dropna(subset=["sp500_close"]).iloc[-2]
sp_change = latest["sp500_close"] - prev["sp500_close"]
sp_change_pct = sp_change / prev["sp500_close"] * 100

# 取引日の米国引け(16:00 ET)を日本時間に変換して「データ基準日」を表示
try:
    _close_et = pd.Timestamp(latest.name).normalize() + pd.Timedelta(hours=16)
    _jst = _close_et.tz_localize("America/New_York").tz_convert("Asia/Tokyo")
    _data_date = _jst.strftime("%Y/%m/%d %H:%M（日本時間）")
except Exception:
    _data_date = pd.Timestamp(latest.name).strftime("%Y/%m/%d")
st.markdown(
    "<div style='text-align:center; font-size:0.85rem; color:#b8b4a8;'>"
    f"※ 下記カードは米国引け <b>{_data_date}</b><br>時点のデータ。<br>"
    f"データ取得時刻：{fetched_at}（日本時間）</div>",
    unsafe_allow_html=True,
)

# --- 1段目: S&P500 → S&P500先物 → 先物乖離 → NASDAQ ---
# スマホは縦1列に積まれるため、この順番がそのまま縦の並びになる。
c1, c2, c3, c4 = st.columns(4)
c1.metric(
    "S&P500（^GSPC・指数）",
    f"{latest['sp500_close']:,.2f}",
    f"{sp_change:+,.2f} ({sp_change_pct:+.2f}%)",
    help="S&P 500 株価指数（米国大型株500社の時価総額加重平均）",
)
card_note(c1, "S&P 500 株価指数")
if "fut_close" in frame.columns:
    fut_now = frame["fut_close"].dropna().iloc[-1]
    fut_prev = frame["fut_close"].dropna().iloc[-2]
    fut_pct = (fut_now - fut_prev) / fut_prev * 100
    c2.metric("S&P500 先物（ES=F）", f"{fut_now:,.2f}", f"{fut_now - fut_prev:+,.2f} ({fut_pct:+.2f}%)", help="S&P500 E-mini 先物（CME上場・ほぼ24時間取引）")
    card_note(c2, "S&P500 E-mini 先物（CME）")
if "fut_gap" in frame.columns:
    gap = frame["fut_gap"].dropna().iloc[-1] * 100
    c3.metric("先物 - 現物 乖離（現在値）", f"{gap:+.2f}%", help="先物が現物より高い=強気センチメントの目安")
if "nasdaq_close" in frame.columns:
    nq_s = frame["nasdaq_close"].dropna()
    nq_chg = nq_s.iloc[-1] - nq_s.iloc[-2]
    nq_pct = nq_chg / nq_s.iloc[-2] * 100
    c4.metric("NASDAQ100（QQQ・米ドル）", f"{nq_s.iloc[-1]:,.2f}", f"{nq_chg:+,.2f} ({nq_pct:+.2f}%)", help="Invesco QQQ Trust（NASDAQ100連動ETF・米ドル建て）")
    card_note(c4, "Invesco QQQ Trust（ETF）")

# --- 2段目: SCHD → オルカン → VIX ---
d1, d2, d3, d4 = st.columns(4)
if "schd_close" in frame.columns:
    schd_s = frame["schd_close"].dropna()
    schd_chg = schd_s.iloc[-1] - schd_s.iloc[-2]
    schd_pct = schd_chg / schd_s.iloc[-2] * 100
    d1.metric("SCHD（米ドル）", f"{schd_s.iloc[-1]:,.2f}", f"{schd_chg:+,.2f} ({schd_pct:+.2f}%)", help="Schwab 米国配当株式 ETF（高配当・連続増配銘柄・米ドル建て）")
    card_note(d1, "Schwab 米国配当株式 ETF")
if "acwi_jp_close" in frame.columns:
    acwi_s = frame["acwi_jp_close"].dropna()
    acwi_chg = acwi_s.iloc[-1] - acwi_s.iloc[-2]
    acwi_pct = acwi_chg / acwi_s.iloc[-2] * 100
    d2.metric("オルカン（ACWI・円換算）", f"{acwi_s.iloc[-1]:,.0f}", f"{acwi_chg:+,.0f} ({acwi_pct:+.2f}%)", help="iShares MSCI ACWI ETF（全世界株式・USD建てをドル円で円換算。eMAXIS Slim 全世界株式のプロキシ）")
    card_note(d2, "iShares MSCI ACWI ETF（円換算）")
if "vix_close" in frame.columns:
    vix_now = frame["vix_close"].dropna().iloc[-1]
    vix_prev = frame["vix_close"].dropna().iloc[-2]
    d3.metric("VIX 指数（^VIX）", f"{vix_now:.2f}", f"{vix_now - vix_prev:+.2f}", delta_color="inverse", help="CBOE ボラティリティ指数（恐怖指数・S&P500の予想変動率）")
    card_note(d3, "CBOE ボラティリティ指数")

# ---- 為替・金利メトリクス ----
m1, m2, m3 = st.columns(3)
if "usdjpy_close" in frame.columns:
    jpy = frame["usdjpy_close"].dropna()
    m1.metric("USD/JPY（前日比）", f"{jpy.iloc[-1]:.2f}", f"{jpy.iloc[-1] - jpy.iloc[-2]:+.2f}")
if "dxy_close" in frame.columns:
    dxy = frame["dxy_close"].dropna()
    m2.metric("ドル指数（対主要通貨・前日比）", f"{dxy.iloc[-1]:.2f}", f"{dxy.iloc[-1] - dxy.iloc[-2]:+.2f}", help="米ドルの主要6通貨に対する強さ（DXY）。上昇=ドル高")
if "curve_spread" in frame.columns:
    cs = frame["curve_spread"].dropna().iloc[-1]
    m3.metric(
        "利回り差（10年-3ヶ月）",
        f"{cs:+.2f}pt",
        "逆イールド" if cs < 0 else "順イールド",
        delta_color="off",
        help="マイナス=逆イールド（景気後退の代表的サイン）",
    )

# ---- 主要金利（米国10年・日本国債3/5/10年）----
st.markdown(
    "<div style='text-align:center; font-size:0.85rem; color:#b8b4a8;'>"
    "主要金利（米国10年債・日本国債）　下段は前日比</div>",
    unsafe_allow_html=True,
)
g1, g2, g3, g4 = st.columns(4)
if "ust10y_close" in frame.columns:
    y10 = frame["ust10y_close"].dropna()
    g1.metric("米国10年金利（^TNX）", f"{y10.iloc[-1]:.3f}%", f"{(y10.iloc[-1] - y10.iloc[-2]):+.3f}pt", delta_color="inverse", help="米国債10年 利回り")
    card_note(g1, "米国債10年 利回り")
_jgb = load_jgb()


def _jgb_card(col, year: str):
    """日本国債の指定年限カードを描画（財務省データ）。"""
    if _jgb is not None and not _jgb.empty and year in _jgb.columns:
        s = _jgb[year].dropna()
        if len(s) >= 2:
            col.metric(f"日本国債{year}", f"{s.iloc[-1]:.3f}%", f"{s.iloc[-1] - s.iloc[-2]:+.3f}pt", delta_color="inverse", help=f"日本国債{year} 利回り（財務省公表値）")
            card_note(col, "財務省 公表利回り")
            return
    col.metric(f"日本国債{year}", "—", help="財務省データを取得できませんでした")


_jgb_card(g2, "3年")
_jgb_card(g3, "5年")
_jgb_card(g4, "10年")

# ---- 日本の短期金利・長期金利（1年/10年国債）----
st.markdown(
    "<div style='text-align:center; font-size:0.85rem; color:#b8b4a8;'>"
    "日本の短期金利・長期金利　下段は前日比</div>",
    unsafe_allow_html=True,
)
h1, h2, h3, h4 = st.columns(4)


def _jp_rate_card(col, label, year, note):
    """日本の短期/長期金利カード（財務省データ）。"""
    if _jgb is not None and not _jgb.empty and year in _jgb.columns:
        s = _jgb[year].dropna()
        if len(s) >= 2:
            col.metric(label, f"{s.iloc[-1]:.3f}%", f"{s.iloc[-1] - s.iloc[-2]:+.3f}pt", delta_color="inverse", help=f"{note}（財務省公表値）")
            card_note(col, note)
            return
    col.metric(label, "—", help="財務省データを取得できませんでした")


_jp_rate_card(h1, "日本 短期金利", "1年", "日本国債1年 利回り")
_jp_rate_card(h2, "日本 長期金利", "10年", "日本国債10年 利回り")

# ---- ドル指数・利回り差の簡潔な解説（9pt 程度の小さめ文字） ----
st.markdown(
    """
    <div style="font-size:9pt; line-height:1.5; color:#d8d4c6; margin-top:4px;">
    ※ <b>ドル指数（対主要通貨）</b>：米ドルの主要6通貨に対する強さ。
    上昇＝ドル高（米企業の海外売上に逆風で株にやや弱気要因）、下落＝ドル安（株・金に追い風）。<br>
    ※ <b>利回り差（10年-3ヶ月）</b>：長期金利−短期金利。
    プラス＝順イールド（正常）、マイナス＝逆イールド（短期金利が長期を上回る異常で、景気後退の代表的な前兆サイン）。
    </div>
    """,
    unsafe_allow_html=True,
)

# ---- VIX チャート ----
if "vix_close" in frame.columns:
    with st.expander("VIX 指数の推移を表示"):
        st.caption(
            "※ VIX指数（恐怖指数）は、S&P500の今後約30日間の予想変動率を示す指標です。"
            "数値が高いほど投資家の不安が大きいことを意味し、相場の下落局面で急上昇します。"
            "目安は20以下＝平常圏、20〜30＝やや警戒、30超＝強い警戒（パニック的な売り）。"
        )
        vfig = go.Figure()
        vfig.add_trace(go.Scatter(x=frame.index, y=frame["vix_close"], name="VIX", line=dict(color="orange")))
        vfig.add_hline(y=20, line_dash="dash", annotation_text="平常圏 20", line_color="gray")
        vfig.add_hline(y=30, line_dash="dash", annotation_text="警戒圏 30", line_color="red")
        vfig.update_layout(
            template="light_chart", paper_bgcolor="#ffffff", plot_bgcolor="#ffffff", font_color="#222222",
            height=320, margin=dict(l=10, r=10, t=10, b=40),
            xaxis_title="期間（月）", yaxis_title="VIX 指数（恐怖指数）",
        )
        monthly_axis(vfig)
        st.caption(CHART_OP_HELP)
        st.plotly_chart(vfig, use_container_width=True, theme=None, config=MOBILE_CONFIG)

# ---- 為替・金利チャート ----
with st.expander("為替・米国10年債の推移を表示"):
    fx_col, yld_col = st.columns(2)
    if "usdjpy_close" in frame.columns or "dxy_close" in frame.columns:
        ffig = go.Figure()
        if "usdjpy_close" in frame.columns:
            ffig.add_trace(go.Scatter(x=frame.index, y=frame["usdjpy_close"], name="USD/JPY"))
        if "dxy_close" in frame.columns:
            ffig.add_trace(go.Scatter(x=frame.index, y=frame["dxy_close"], name="DXY", yaxis="y2"))
        ffig.update_layout(
            template="light_chart", paper_bgcolor="#ffffff", plot_bgcolor="#ffffff", font_color="#222222",
            title="為替", height=320, margin=dict(l=10, r=10, t=40, b=40),
            xaxis_title="期間（月）",
            yaxis=dict(title="USD/JPY（円）"),
            yaxis2=dict(title="ドル指数（対主要通貨）", overlaying="y", side="right", showgrid=False),
            legend=dict(orientation="h", y=1.1, x=0),
        )
        monthly_axis(ffig)
        fx_col.caption(CHART_OP_HELP)
        fx_col.plotly_chart(ffig, use_container_width=True, theme=None, config=MOBILE_CONFIG)
    if "ust10y_close" in frame.columns:
        yfig = go.Figure()
        yfig.add_trace(go.Scatter(x=frame.index, y=frame["ust10y_close"], name="10年", line=dict(color="crimson")))
        if "ust3m_close" in frame.columns:
            yfig.add_trace(go.Scatter(x=frame.index, y=frame["ust3m_close"], name="3ヶ月", line=dict(color="steelblue")))
        yfig.update_layout(
            template="light_chart", paper_bgcolor="#ffffff", plot_bgcolor="#ffffff", font_color="#222222",
            title="米国10年債 利回り (%)", height=340, margin=dict(l=10, r=10, t=40, b=40),
            xaxis_title="期間（月）", yaxis_title="利回り (%)",
            legend=dict(orientation="h", y=1.1, x=0),
        )
        monthly_axis(yfig)
        yld_col.caption(CHART_OP_HELP)
        yld_col.plotly_chart(yfig, use_container_width=True, theme=None, config=MOBILE_CONFIG)

st.markdown("---")

# ---- 資産タブ（S&P500 / SCHD を並列に: チャート + 予測強化） ----
FEAT_LABELS = {
    "own_ret": "前日リターン",
    "ma_gap_5": "5日移動平均乖離",
    "ma_gap_20": "20日移動平均乖離",
    "vol_5": "5日ボラティリティ",
    "vix_close": "VIX 水準",
    "vix_chg": "VIX 変化",
    "fut_ret": "先物リターン",
    "fut_gap": "先物-現物乖離",
    "usdjpy_ret": "ドル円リターン",
    "dxy_ret": "ドル指数リターン",
    "ust10y_chg": "米国10年債 変化",
    "curve_spread": "10年-3ヶ月スプレッド",
}


def render_asset(asset_key: str, name: str, close_col: str, ret_col: str):
    """1資産分のローソク足チャートと予測（強化版）を描画する。"""
    # --- 価格チャート ---
    section_title(name)
    ohlc = raw.get(asset_key)
    if ohlc is None or ohlc.empty:
        st.info(f"{name} の価格データを取得できませんでした。")
    else:
        ohlc = ohlc.copy()
        if isinstance(ohlc.columns, pd.MultiIndex):
            ohlc.columns = ohlc.columns.get_level_values(0)
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=ohlc.index, y=ohlc["Close"], name=name,
                line=dict(color="#1f77b4", width=1.8),
            )
        )
        fig.update_layout(
            template="light_chart", paper_bgcolor="#ffffff", plot_bgcolor="#ffffff", font_color="#222222",
            height=460, xaxis_rangeslider_visible=False,
            margin=dict(l=10, r=10, t=10, b=40),
            legend=dict(orientation="h", y=1.02, x=0),
        )
        monthly_axis(fig)
        st.caption(CHART_OP_HELP)
        st.plotly_chart(fig, use_container_width=True, theme=None, config=MOBILE_CONFIG)

    # --- 予測（翌日 + 区間 + 複数日 + 的中履歴） ---
    section_title(f"{name}予測")
    pred = model_mod.predict_asset(frame, close_col, ret_col, name)
    if pred is None:
        st.info("予測に十分なデータがありません。表示期間を長くして再度お試しください。")
        return

    pc1, pc2, pc3 = st.columns(3)
    pc1.metric("予測方向", pred.direction, f"{pred.pred_return * 100:+.2f}%")
    pc2.metric(
        "予測終値（目安）", f"{pred.pred_close:,.2f}",
        f"{pred.pred_return * 100:+.2f}%", help=f"直近終値 {pred.last_close:,.2f}",
    )
    pc3.metric("信頼度", pred.confidence, help="検証期間の方向的中率に基づく")
    st.caption(
        f"※ 翌日の予測区間（約80%）: **{pred.pred_low:,.2f} 〜 {pred.pred_high:,.2f}**"
    )

    if pred.direction_hit == pred.direction_hit:  # not NaN
        st.caption(
            f"※ アンサンブル検証: 方向的中率 **{pred.direction_hit * 100:.1f}%** / "
            f"平均絶対誤差 **{pred.backtest_mae * 100:.2f}%**（学習 {pred.n_train} 営業日）。"
            f"的中率50%付近はコイン投げと同等で、予測の確実性は低いことを意味します。"
        )

    # --- 複数日先の予測 ---
    if pred.multiday:
        with st.expander(f"複数日先（{len(pred.multiday)}営業日）の見通しレンジ"):
            days = [0] + [m["day"] for m in pred.multiday]
            mid = [pred.last_close] + [m["close"] for m in pred.multiday]
            low = [pred.last_close] + [m["low"] for m in pred.multiday]
            high = [pred.last_close] + [m["high"] for m in pred.multiday]
            mfig = go.Figure()
            mfig.add_trace(go.Scatter(x=days, y=high, name="上限", line=dict(width=0), showlegend=False))
            mfig.add_trace(go.Scatter(
                x=days, y=low, name="予測レンジ(約80%)", fill="tonexty",
                fillcolor="rgba(212,175,55,0.18)", line=dict(width=0),
            ))
            mfig.add_trace(go.Scatter(x=days, y=mid, name="中心予測", line=dict(color="#E9C766", width=2)))
            mfig.update_layout(
                template="light_chart", paper_bgcolor="#ffffff", plot_bgcolor="#ffffff", font_color="#222222",
                height=320, margin=dict(l=10, r=10, t=10, b=10),
                xaxis_title="何営業日先か（0=直近）", yaxis_title="予測終値（目安）",
                legend=dict(orientation="h", y=1.1, x=0),
            )
            st.caption(CHART_OP_HELP)
            st.plotly_chart(mfig, use_container_width=True, theme=None, config=MOBILE_CONFIG)
            st.caption("※ 日次ドリフトが継続すると仮定した単純投影。先になるほど不確実性（レンジ幅）は拡大します。")

    # --- 的中履歴グラフ ---
    if pred.bt_dates:
        with st.expander("予測の的中履歴（バックテスト）"):
            hb1 = go.Figure()
            hb1.add_trace(go.Scatter(x=pred.bt_dates, y=pred.bt_actual_close, name="実際の終値", line=dict(color="#7FB8FF")))
            hb1.add_trace(go.Scatter(x=pred.bt_dates, y=pred.bt_pred_close, name="予測終値", line=dict(color="#E9C766", dash="dot")))
            hb1.update_layout(
                template="light_chart", paper_bgcolor="#ffffff", plot_bgcolor="#ffffff", font_color="#222222",
                title="予測 vs 実際（検証期間）", height=300,
                margin=dict(l=10, r=10, t=40, b=10),
                xaxis_title="日付", yaxis_title="終値",
                legend=dict(orientation="h", y=1.12, x=0),
            )
            st.caption(CHART_OP_HELP)
            st.plotly_chart(hb1, use_container_width=True, theme=None, config=MOBILE_CONFIG)

            hb2 = go.Figure()
            hb2.add_trace(go.Scatter(x=pred.bt_dates, y=pred.bt_roll_hit, name="方向的中率(20日移動)", line=dict(color="#2ca02c")))
            hb2.add_hline(y=50, line_dash="dash", line_color="gray", annotation_text="コイン投げ 50%")
            hb2.update_layout(
                template="light_chart", paper_bgcolor="#ffffff", plot_bgcolor="#ffffff", font_color="#222222",
                title="方向的中率の推移 (%)", height=260,
                margin=dict(l=10, r=10, t=40, b=10),
                xaxis_title="日付", yaxis=dict(range=[0, 100], title="方向的中率 (%)"),
            )
            st.caption(CHART_OP_HELP)
            st.plotly_chart(hb2, use_container_width=True, theme=None, config=MOBILE_CONFIG)

    # --- 特徴量重要度 ---
    with st.expander("どの指標の予測ウエイトが高いか"):
        imp = pd.Series(pred.feature_importance).sort_values(ascending=True)
        imp.index = [FEAT_LABELS.get(i, i) for i in imp.index]
        ifig = go.Figure(go.Bar(x=imp.values, y=imp.index, orientation="h", marker_color="#D4AF37"))
        ifig.update_layout(
            template="light_chart", paper_bgcolor="#ffffff", plot_bgcolor="#ffffff", font_color="#222222",
            height=340, margin=dict(l=10, r=10, t=10, b=10),
            xaxis_title="重要度（予測への寄与の大きさ）", yaxis_title="指標",
        )
        st.caption(CHART_OP_HELP)
        st.plotly_chart(ifig, use_container_width=True, theme=None, config=MOBILE_CONFIG)


st.markdown(
    "<div style='text-align:center; font-weight:700; color:#E9C766; "
    "font-size:1.8rem; margin:0.3em 0;'>Index chart</div>",
    unsafe_allow_html=True,
)
tab_sp, tab_nasdaq, tab_schd, tab_acwi = st.tabs(
    ["① S&P500", "② NASDAQ100", "③ SCHD", "④ 全世界株式(オルカン)"]
)
with tab_sp:
    render_asset("sp500", "S&P500", "sp500_close", "sp500_ret")
with tab_nasdaq:
    if "nasdaq_close" in frame.columns:
        render_asset("nasdaq", "NASDAQ100", "nasdaq_close", "nasdaq_ret")
    else:
        st.info("NASDAQ のデータを取得できませんでした。")
with tab_schd:
    if "schd_close" in frame.columns:
        render_asset("schd", "SCHD", "schd_close", "schd_ret")
    else:
        st.info("SCHD のデータを取得できませんでした。")
with tab_acwi:
    st.caption(
        "🌍 **eMAXIS Slim 全世界株式（オール・カントリー）のプロキシ**。投資信託そのものは"
        "yfinanceで取得できないため、本家 **MSCI ACWI 連動の ACWI ETF（USD）をドル円で円換算** "
        "した合成指数（円建て）を表示しています。同じ指数・同じ円建てのため値動きはほぼ連動します。"
    )
    if "acwi_jp_close" in frame.columns:
        render_asset("acwi_jp", "全世界株式(オルカン)", "acwi_jp_close", "acwi_jp_ret")
    else:
        st.info("全世界株式のデータを取得できませんでした。")

st.markdown("---")

# ---- 組み入れ銘柄（組入銘柄・セクター構成） ----
st.markdown(
    "<div style='text-align:center; font-weight:700; color:#E9C766; "
    "font-size:1.8rem; margin:0.3em 0;'>Index 構成概要</div>",
    unsafe_allow_html=True,
)
st.caption(
    "それぞれのファンドが「どんな会社」に「どの業種に」どれくらい投資しているかの内訳です。"
    "S&P500は米国大型株、SCHDは米国の高配当・割安株、オルカンは全世界の株式に分散投資します。"
)


def render_fund_profile(name: str, ticker: str):
    """1ファンドの組入上位銘柄テーブルとセクター構成円グラフを描画する。"""
    prof = load_fund_profile(ticker)
    st.markdown(
        f"<h4 style='text-align:center;'>{name}（{ticker} ベース）</h4>",
        unsafe_allow_html=True,
    )
    # 左にセクター構成比率、右に組入上位銘柄（位置を入れ替え）
    col_s, col_h = st.columns([1, 1])

    # 組入上位銘柄
    with col_h:
        st.markdown(
            "<div style='text-align:center; font-weight:700;'>組入 上位銘柄</div>",
            unsafe_allow_html=True,
        )
        hold = prof.get("holdings")
        if hold is None or (hasattr(hold, "empty") and hold.empty):
            st.info("組入銘柄データを取得できませんでした。")
        else:
            tbl = hold.reset_index()
            # 列名を正規化（APIバージョンによって列名が異なる場合に対応）
            cols = tbl.columns.tolist()
            rename_map = {}
            for i, c in enumerate(cols):
                cl = str(c).lower()
                if i == 0 or "symbol" in cl or cl in ("index", "ticker"):
                    rename_map[c] = "シンボル"
                elif "name" in cl or "holding" in cl and "percent" not in cl:
                    rename_map[c] = "銘柄名"
                elif "percent" in cl or "weight" in cl or "value" in cl:
                    rename_map[c] = "構成比"
            tbl = tbl.rename(columns=rename_map)
            if "構成比" in tbl.columns:
                tbl["構成比"] = (tbl["構成比"] * 100).round(2).astype(str) + "%"

            # 各行を、その銘柄の所属業種の色（業種構成比率と同じ配色）で薄く塗る
            def _row_sector_style(row):
                sym = str(row.get("シンボル", "")).strip().upper()
                key = STOCK_SECTOR.get(sym)
                color = SECTOR_COLORS.get(key) if key else None
                # 業種構成比率(円グラフ)と同じ色をそのまま使用。
                # 文字色は背景の明暗に応じて黒/白を自動選択。
                if color:
                    fg = _text_on(color)
                    return [f"background-color: {color}; color: {fg}"] * len(row)
                return ["background-color: #cccccc; color: #1a1a1a"] * len(row)

            styled = tbl.style.apply(_row_sector_style, axis=1)
            st.dataframe(styled, use_container_width=True, hide_index=True, height=400)
            if prof.get("is_static"):
                st.caption("※ 参考値（2026年6月時点の概算）。最新構成比は各ETF公式サイトでご確認ください。")
            else:
                st.caption("※ 無料データソース（Yahoo）の制約で上位約10銘柄まで表示。")

    # セクター構成円グラフ
    with col_s:
        st.markdown(
            "<div style='text-align:center; font-weight:700; color:#E9C766; "
            "font-size:1.2rem;'>業種構成比率</div>",
            unsafe_allow_html=True,
        )
        sectors = prof.get("sectors")
        if not sectors:
            st.info("業種構成データを取得できませんでした。")
        else:
            # (英語キー, 日本語ラベル, 比率) で保持し、色は英語キー基準で固定する
            items = [(k, data_mod.SECTOR_JP.get(k, k), v) for k, v in sectors.items() if v and v > 0]
            items.sort(key=lambda x: x[2], reverse=True)
            labels = [i[1] for i in items]
            values = [i[2] * 100 for i in items]
            # 業種ごとに固定色を割り当て（全ファンドで同じ業種＝同じ色）
            colors = [SECTOR_COLORS.get(i[0], "#9aa0a6") for i in items]
            pie = go.Figure(
                go.Pie(
                    labels=labels, values=values, hole=0.4,
                    textinfo="label+percent", textposition="inside",
                    sort=False, marker=dict(colors=colors),
                )
            )
            pie.update_layout(
                template="light_chart", paper_bgcolor="#ffffff", plot_bgcolor="#ffffff", font_color="#222222",
                height=400, margin=dict(l=10, r=10, t=10, b=10),
                showlegend=True, legend=dict(orientation="v", x=1.0, y=0.5),
            )
            st.caption(CHART_OP_HELP)
            st.plotly_chart(pie, use_container_width=True, key=f"pie_{ticker}", theme=None, config=MOBILE_CONFIG)


ftab1, ftab2, ftab3, ftab4 = st.tabs(["① S&P500", "② NASDAQ100", "③ SCHD", "④ オルカン"])
with ftab1:
    render_fund_profile("S&P500", data_mod.FUND_PROXIES["S&P500"])
with ftab2:
    render_fund_profile("NASDAQ100", data_mod.FUND_PROXIES["NASDAQ"])
with ftab3:
    render_fund_profile("SCHD", data_mod.FUND_PROXIES["SCHD"])
with ftab4:
    render_fund_profile("オルカン（全世界株式）", data_mod.FUND_PROXIES["オルカン"])

st.markdown("---")

# ---- ETF パフォーマンス・パネル（汎用） ----
def render_etf_panel(
    title: str, name_map: dict, label_col: str, bar_title: str, chart_key: str,
    baseline_period: float | None = None, baseline_day: float | None = None,
    sort_col: str = "前日比 %", show_bar: bool = True, heading_small: bool = False,
    table_first: bool = False, subtitle: str | None = None,
    heading_size: str = "1.2rem", period_note: bool = False,
    bar_colors: dict | None = None,
):
    """指定ETF群の前日比・期間騰落を棒グラフ＋テーブルで描画する。

    baseline_period / baseline_day を渡すと、それぞれ
    「対S&P500(期間)」「対S&P500(前日比)」の相対パフォーマンス列を追加する。
    heading_small=True で見出しを「セクター構成比率」と同じ小さめ金文字にする。
    """
    if heading_small:
        st.markdown(
            f"<div style='text-align:center; font-weight:700; color:#E9C766; "
            f"font-size:{heading_size}; margin:0.3em 0;'>{title}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.subheader(title)
    if subtitle:
        st.markdown(
            f"<div style='text-align:center; font-weight:700; color:#E9C766; "
            f"font-size:1.2rem; margin:0.1em 0 0.4em 0;'>{subtitle}</div>",
            unsafe_allow_html=True,
        )
    closes = load_group(tuple(name_map.keys()), period)
    if closes.empty:
        st.info("データを取得できませんでした。")
        return
    valid = closes.dropna(how="all")
    last_row, prev_row, first_row = valid.iloc[-1], valid.iloc[-2], valid.iloc[0]
    rel_p_col = "対S&P500(期間) %"
    rel_d_col = "対S&P500(前日比) %"
    rows = []
    for ticker in closes.columns:
        if pd.isna(last_row.get(ticker)) or pd.isna(prev_row.get(ticker)):
            continue
        day_chg = (last_row[ticker] / prev_row[ticker] - 1) * 100
        period_chg = (last_row[ticker] / first_row[ticker] - 1) * 100
        row = {
            "_ticker": ticker,
            label_col: f"{name_map.get(ticker, ticker)} ({ticker})",
            "前日比 %": day_chg,
            PERIOD_COL: period_chg,
        }
        if baseline_day is not None:
            row[rel_d_col] = day_chg - baseline_day
        if baseline_period is not None:
            row[rel_p_col] = period_chg - baseline_period
        rows.append(row)
    df = pd.DataFrame(rows).sort_values(sort_col, ascending=False)

    fmt = {"前日比 %": "{:+.2f}", PERIOD_COL: "{:+.2f}"}
    if baseline_day is not None:
        fmt[rel_d_col] = "{:+.2f}"
    if baseline_period is not None:
        fmt[rel_p_col] = "{:+.2f}"

    # 表示用は内部列 _ticker を除く
    df_disp = df.drop(columns=["_ticker"])
    _order = df["_ticker"].tolist()

    def _styled_table(df_show):
        """fmt整形＋（bar_colors指定時）行を業種色で塗ったStylerを返す。"""
        sty = df_show.style.format(fmt)
        if bar_colors:
            def _row_c(row):
                pos = df_show.index.get_indexer([row.name])[0]
                c = bar_colors.get(_order[pos])
                if not c:
                    return [""] * len(row)  # 対応色なし→そのまま（黒）
                # 値が (背景, 文字色) のタプルなら個別指定、文字列なら背景色＋自動文字色
                if isinstance(c, (tuple, list)):
                    bg, fg = c
                else:
                    bg, fg = c, _text_on(c)
                return [f"background-color: {bg}; color: {fg}"] * len(row)
            sty = sty.apply(_row_c, axis=1)
        return sty

    if not show_bar:
        # グラフなし: テーブルのみ全幅表示
        st.dataframe(_styled_table(df_disp), use_container_width=True, hide_index=True)
        return

    # bar_colors（ティッカー→色）が指定されていれば業種色、無ければ騰落の緑/赤
    if bar_colors:
        marker_color = [bar_colors.get(t, "#888888") for t in df["_ticker"]]
    else:
        marker_color = ["#2ca02c" if v >= 0 else "#d62728" for v in df[sort_col]]
    bar = go.Figure(
        go.Bar(
            x=df[sort_col], y=df[label_col], orientation="h",
            marker_color=marker_color,
        )
    )
    bar.update_layout(
        template="light_chart", paper_bgcolor="#ffffff", plot_bgcolor="#ffffff", font_color="#222222",
        title=bar_title, height=max(320, 32 * len(df)),
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis_title=f"{sort_col}（リターン）", yaxis=dict(title=label_col, autorange="reversed"),
    )
    # table_first=True なら 表を左・グラフを右 に入れ替える
    if table_first:
        tbl_col, bar_col = st.columns([2, 3])
    else:
        bar_col, tbl_col = st.columns([3, 2])
    bar_col.plotly_chart(bar, use_container_width=True, key=chart_key, theme=None, config=MOBILE_CONFIG)
    bar_col.caption(CHART_OP_HELP)
    tbl_col.dataframe(_styled_table(df_disp), use_container_width=True, hide_index=True)
    if period_note:
        tbl_col.caption("※ 騰落期間（6mo/1y/3y/5y/10y）を変更するには左上の >> から期間を変更してください")


# セクター別 ETF
render_etf_panel(
    "業種別 パフォーマンス",
    data_mod.SECTOR_ETFS, "業種",
    "前日比リターン（業種別）", "sector_bar",
    heading_small=True, table_first=True, subtitle="《参考資料》",
    heading_size="1.8rem", period_note=True, bar_colors=SECTOR_ETF_COLORS,
)
st.markdown("---")

# ディフェンシブ／資金逃避先（S&P500 との相対パフォーマンス付き）
sp_series = frame["sp500_close"].dropna()
sp_day_chg = (sp_series.iloc[-1] / sp_series.iloc[-2] - 1) * 100
render_etf_panel(
    "資金逃避先",
    data_mod.DEFENSIVE_ETFS, "資産",
    "対S&P500 期間リターン差（ディフェンシブ）", "defensive_bar",
    baseline_day=sp_day_chg,
    sort_col="前日比 %", show_bar=False, heading_small=True, subtitle="《参考資料》",
    heading_size="1.8rem", bar_colors=DEFENSIVE_ETF_COLORS,
)
st.markdown(
    """
    <div style="font-size:9pt; line-height:1.6; color:#d8d4c6;">
    ※ <b>「対S&P500（前日比）」</b>は、その資産が前日比でS&P500より何％多く動いたか（相対パフォーマンス）を表します。<br>
    ・<b>プラス（＋）</b>＝S&P500より強い＝資金がその資産に逃げている可能性（リスク回避＝リスクオフのサイン）<br>
    ・<b>マイナス（−）</b>＝S&P500より弱い＝リスクオン（株が選好されている）<br>
    S&P500が下がる局面で金・米国債・公益株などが「対S&P500プラス」になっていれば、投資家がこちらに資金を移している目安になります。
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("---")

# ---- 経済ニュース ----
st.markdown(
    "<div style='text-align:center; font-weight:700; color:#E9C766; "
    "font-size:1.8rem; margin:0.3em 0;'>金利・株価ニュース</div>",
    unsafe_allow_html=True,
)
st.caption(
    "金利・株価に関する見出しに絞って表示しています。"
    "国内はNHK・Yahoo!ニュース（日本語）、米国S&P500関連は米国Yahoo Finance（英語＋日本語訳を併記）から取得。"
)
items = load_news()
if not items:
    st.info("ニュースを取得できませんでした。時間をおいて更新してください。")
else:
    def _esc(s: str) -> str:
        # $ は Streamlit の数式記法($...$)に誤解釈されるためエスケープ
        return (s or "").replace("$", "\\$")

    for it in items:
        title = _esc(it["title"])
        # 英語見出しに日本語訳が取れていれば下に併記
        ja = _esc(it.get("title_ja"))
        src = f"{it['source']} ｜ {it['published']}"
        sub = f"🇯🇵 {ja}<br>{src}" if ja else src
        st.markdown(
            f"- [{title}]({it['link']})  \n  <small>{sub}</small>",
            unsafe_allow_html=True,
        )

st.markdown("---")

# ---- 積み立て＆取り崩しシミュレーション（外部サイト）----
st.markdown(
    "<div style='text-align:center; margin:0.3em 0;'>"
    "<span style='font-weight:700; color:#E9C766; font-size:1.8rem;'>"
    "積み立て＆取り崩し<br>シミュレーション</span><br>"
    "<span style='font-weight:700; color:#E9C766; font-size:0.9rem;'>（MUFG外部サイト）</span>"
    "</div>",
    unsafe_allow_html=True,
)
st.link_button(
    "シミュレーションはこちら ▶",
    "https://www.am.mufg.jp/tool/simulation_tsumitate.html",
    use_container_width=True,
)

st.markdown("---")

# ---- 無料 ChatGPT（外部サイト）----
st.markdown(
    "<div style='text-align:center; font-weight:700; color:#E9C766; "
    "font-size:1.8rem; margin:0.3em 0;'>AIに相談する</div>"
    "<div style='text-align:center; font-size:0.85rem; color:#b8b4a8;'>"
    "わからない用語や投資の疑問を無料のChatGPTに聞けます（別タブで開きます）</div>",
    unsafe_allow_html=True,
)
st.link_button(
    "無料ChatGPTを開く ▶",
    "https://chatgpt.com/",
    use_container_width=True,
)

# ---- 注意書き・免責事項（最下部）----
st.markdown("---")
st.caption(
    "本アプリはyfinance（無料データ）を利用しています。データには遅延・欠損が含まれる場合があります。"
    "表示・予測は情報提供のみを目的とし、投資勧誘や成果保証ではありません。"
)
st.caption(
    "⚠️ **免責事項**：本アプリの情報・予測値は過去データに基づく参考シグナルであり、"
    "将来の運用成果を保証するものではありません。特定銘柄の売買を推奨・勧誘するものではなく、"
    "投資判断はご自身の責任で行ってください。本アプリの利用により生じたいかなる損害についても"
    "制作者は責任を負いません。"
)
