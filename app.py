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
    page_title="Index 投資は楽しい by よしけい",
    layout="wide", page_icon="🪙",
    initial_sidebar_state="collapsed",  # スマホで本文を広く使う
)

# スマホ向け: チャートのツールバーを隠しレスポンシブ化（指スクロールを優先）
MOBILE_CONFIG = {"displayModeBar": False, "responsive": True, "scrollZoom": False}

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
            <span style="top:7%;  left:3%;">🪙</span>
            <span style="top:20%; left:90%;">🪙</span>
            <span style="top:38%; left:12%;">🪙</span>
            <span style="top:54%; left:84%;">🪙</span>
            <span style="top:70%; left:28%;">🪙</span>
            <span style="top:84%; left:64%;">🪙</span>
            <span style="top:12%; left:52%;">🪙</span>
            <span style="top:46%; left:44%;">🪙</span>
            <span style="top:90%; left:8%;">🪙</span>
            <span style="top:30%; left:70%;">🪙</span>
            <span style="top:62%; left:4%;">🪙</span>
            <span style="top:4%;  left:76%;">🪙</span>
            <span style="top:77%; left:46%;">🪙</span>
            <span style="top:26%; left:30%;">🪙</span>
            <span style="top:58%; left:60%;">🪙</span>
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
    return raw, frame


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
st.sidebar.title("⚙️ 設定")
period = st.sidebar.selectbox(
    "表示期間",
    options=["6mo", "1y", "3y", "5y", "max"],
    index=2,
    format_func=lambda x: {"6mo": "6ヶ月", "1y": "1年", "3y": "3年", "5y": "5年", "max": "全期間"}[x],
)
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
raw, frame = load_data(period)

st.markdown(
    """
    <div style="text-align:center; font-weight:700; color:#E9C766;
                font-size:clamp(1.3rem, 5vw, 2.3rem); line-height:1.2; margin:0;
                white-space:nowrap;">
        Index 投資は楽しい
    </div>
    <div style="text-align:center; font-weight:700; color:#E9C766;
                font-size:clamp(1.2rem, 4vw, 1.7rem); margin:0.15em 0 0.3em 0;">
        by よしけい
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    "<div style='text-align:center; font-size:0.85rem; color:#b8b4a8;'>"
    "※ 最下部まで読み込むのに数秒かかります。</div>",
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

st.markdown(
    "<div style='text-align:center; font-size:0.85rem; color:#b8b4a8;'>"
    "※ 各カードの下段の増減はいずれも <b>前日比</b> です。</div>",
    unsafe_allow_html=True,
)

# --- 主要4資産 ---
c1, c2, c3, c4 = st.columns(4)
c1.metric(
    "S&P500（前日比）",
    f"{latest['sp500_close']:,.2f}",
    f"{sp_change:+,.2f} ({sp_change_pct:+.2f}%)",
)
if "nasdaq_close" in frame.columns:
    nq_s = frame["nasdaq_close"].dropna()
    nq_chg = nq_s.iloc[-1] - nq_s.iloc[-2]
    nq_pct = nq_chg / nq_s.iloc[-2] * 100
    c2.metric("NASDAQ100（前日比）", f"{nq_s.iloc[-1]:,.2f}", f"{nq_chg:+,.2f} ({nq_pct:+.2f}%)")
if "schd_close" in frame.columns:
    schd_s = frame["schd_close"].dropna()
    schd_chg = schd_s.iloc[-1] - schd_s.iloc[-2]
    schd_pct = schd_chg / schd_s.iloc[-2] * 100
    c3.metric("SCHD（前日比）", f"{schd_s.iloc[-1]:,.2f}", f"{schd_chg:+,.2f} ({schd_pct:+.2f}%)")
if "acwi_jp_close" in frame.columns:
    acwi_s = frame["acwi_jp_close"].dropna()
    acwi_chg = acwi_s.iloc[-1] - acwi_s.iloc[-2]
    acwi_pct = acwi_chg / acwi_s.iloc[-2] * 100
    c4.metric("オルカン・円建（前日比）", f"{acwi_s.iloc[-1]:,.0f}", f"{acwi_chg:+,.0f} ({acwi_pct:+.2f}%)")

# --- 市場環境指標 ---
d1, d2, d3 = st.columns(3)
if "vix_close" in frame.columns:
    vix_now = frame["vix_close"].dropna().iloc[-1]
    vix_prev = frame["vix_close"].dropna().iloc[-2]
    d1.metric("VIX 指数（前日比）", f"{vix_now:.2f}", f"{vix_now - vix_prev:+.2f}", delta_color="inverse")
if "fut_close" in frame.columns:
    fut_now = frame["fut_close"].dropna().iloc[-1]
    fut_prev = frame["fut_close"].dropna().iloc[-2]
    d2.metric("S&P500 先物 ES（前日比）", f"{fut_now:,.2f}", f"{fut_now - fut_prev:+,.2f}")
if "fut_gap" in frame.columns:
    gap = frame["fut_gap"].dropna().iloc[-1] * 100
    d3.metric("先物 - 現物 乖離（現在値）", f"{gap:+.2f}%", help="先物が現物より高い=強気センチメントの目安")

# ---- 為替・金利メトリクス ----
m1, m2, m3, m4 = st.columns(4)
if "usdjpy_close" in frame.columns:
    jpy = frame["usdjpy_close"].dropna()
    m1.metric("USD/JPY（前日比）", f"{jpy.iloc[-1]:.2f}", f"{jpy.iloc[-1] - jpy.iloc[-2]:+.2f}")
if "dxy_close" in frame.columns:
    dxy = frame["dxy_close"].dropna()
    m2.metric("ドル指数（対主要通貨・前日比）", f"{dxy.iloc[-1]:.2f}", f"{dxy.iloc[-1] - dxy.iloc[-2]:+.2f}", help="米ドルの主要6通貨に対する強さ（DXY）。上昇=ドル高")
if "ust10y_close" in frame.columns:
    y10 = frame["ust10y_close"].dropna()
    m3.metric("米国10年債（前日差）", f"{y10.iloc[-1]:.2f}%", f"{(y10.iloc[-1] - y10.iloc[-2]):+.2f}pt", delta_color="inverse")
if "curve_spread" in frame.columns:
    cs = frame["curve_spread"].dropna().iloc[-1]
    m4.metric(
        "利回り差（10年-3ヶ月）",
        f"{cs:+.2f}pt",
        "逆イールド" if cs < 0 else "順イールド",
        delta_color="off",
        help="マイナス=逆イールド（景気後退の代表的サイン）",
    )

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
            go.Candlestick(
                x=ohlc.index, open=ohlc["Open"], high=ohlc["High"],
                low=ohlc["Low"], close=ohlc["Close"], name=name,
            )
        )
        fig.add_trace(go.Scatter(x=ohlc.index, y=ohlc["Close"].rolling(20).mean(), name="MA20", line=dict(width=1)))
        fig.add_trace(go.Scatter(x=ohlc.index, y=ohlc["Close"].rolling(50).mean(), name="MA50", line=dict(width=1)))
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
    "font-size:1.8rem; margin:0.3em 0;'>index chart</div>",
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
section_title("index組み入れ銘柄")
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
            st.dataframe(tbl, use_container_width=True, hide_index=True, height=400)
            if prof.get("is_static"):
                st.caption("※ 参考値（2026年6月時点の概算）。最新構成比は各ETF公式サイトでご確認ください。")
            else:
                st.caption("※ 無料データソース（Yahoo）の制約で上位約10銘柄まで表示。")

    # セクター構成円グラフ
    with col_s:
        st.markdown(
            "<div style='text-align:center; font-weight:700; color:#E9C766; "
            "font-size:1.2rem;'>セクター構成比率</div>",
            unsafe_allow_html=True,
        )
        sectors = prof.get("sectors")
        if not sectors:
            st.info("セクター構成データを取得できませんでした。")
        else:
            items = [(data_mod.SECTOR_JP.get(k, k), v) for k, v in sectors.items() if v and v > 0]
            items.sort(key=lambda x: x[1], reverse=True)
            labels = [i[0] for i in items]
            values = [i[1] * 100 for i in items]
            pie = go.Figure(
                go.Pie(
                    labels=labels, values=values, hole=0.4,
                    textinfo="label+percent", textposition="inside",
                    sort=False,
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
):
    """指定ETF群の前日比・期間騰落を棒グラフ＋テーブルで描画する。

    baseline_period / baseline_day を渡すと、それぞれ
    「対S&P500(期間)」「対S&P500(前日比)」の相対パフォーマンス列を追加する。
    heading_small=True で見出しを「セクター構成比率」と同じ小さめ金文字にする。
    """
    if heading_small:
        section_title(title)
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
            label_col: f"{name_map.get(ticker, ticker)} ({ticker})",
            "前日比 %": day_chg,
            "期間騰落 %": period_chg,
        }
        if baseline_day is not None:
            row[rel_d_col] = day_chg - baseline_day
        if baseline_period is not None:
            row[rel_p_col] = period_chg - baseline_period
        rows.append(row)
    df = pd.DataFrame(rows).sort_values(sort_col, ascending=False)

    fmt = {"前日比 %": "{:+.2f}", "期間騰落 %": "{:+.2f}"}
    if baseline_day is not None:
        fmt[rel_d_col] = "{:+.2f}"
    if baseline_period is not None:
        fmt[rel_p_col] = "{:+.2f}"

    if not show_bar:
        # グラフなし: テーブルのみ全幅表示
        st.dataframe(df.style.format(fmt), use_container_width=True, hide_index=True)
        return

    bar = go.Figure(
        go.Bar(
            x=df[sort_col], y=df[label_col], orientation="h",
            marker_color=["#2ca02c" if v >= 0 else "#d62728" for v in df[sort_col]],
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
    tbl_col.dataframe(df.style.format(fmt), use_container_width=True, hide_index=True)


# セクター別 ETF
render_etf_panel(
    "セクター別 ETF パフォーマンス",
    data_mod.SECTOR_ETFS, "セクター",
    "前日比リターン（セクター別）", "sector_bar",
    heading_small=True, table_first=True, subtitle="《参考資料》",
)
st.markdown("---")

# ディフェンシブ／資金逃避先（S&P500 との相対パフォーマンス付き）
sp_series = frame["sp500_close"].dropna()
sp_day_chg = (sp_series.iloc[-1] / sp_series.iloc[-2] - 1) * 100
render_etf_panel(
    "ディフェンシブ / 資金逃避先",
    data_mod.DEFENSIVE_ETFS, "資産",
    "対S&P500 期間リターン差（ディフェンシブ）", "defensive_bar",
    baseline_day=sp_day_chg,
    sort_col="期間騰落 %", show_bar=False, heading_small=True, subtitle="《参考資料》",
)
st.caption(
    "※ **S&P500 が不調なときに資金が向かいやすい先**（ディフェンシブ）。"
    "公益・生活必需品・ヘルスケア・エネルギーは SCHD の主要構成セクターとも重なります。"
    f"「対S&P500(前日比)」がプラス＝S&P500（前日比 {sp_day_chg:+.2f}%）を上回っており、"
    "「リスク回避（資金逃避）」が起きているサインの目安です。"
)

st.markdown("---")

# ---- 経済ニュース ----
section_title("経済・国際ニュース（金利・株価）")
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
