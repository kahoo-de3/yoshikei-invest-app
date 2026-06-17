"""翌日・複数日先の予測モデル（統計 + 軽量MLアンサンブル）。

重要な前提:
    株価の将来値を正確に当てることは原理的に不可能です。
    このモデルが出すのは「過去データ・VIX・先物・為替・金利などから推定した
    参考シグナル」であり、投資判断を保証するものではありません。

アプローチ:
    対象資産（S&P500 / SCHD など）の特徴量から翌日リターンを
    複数モデルのアンサンブル（勾配ブースティング・ランダムフォレスト・
    Extra Trees）で回帰予測する。時系列なので shuffle せず、
    過去で学習し直近で検証して精度の目安・的中履歴・予測区間を出す。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.ensemble import (
    ExtraTreesRegressor,
    GradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.metrics import mean_absolute_error

# 対象資産そのものから作る特徴量
ASSET_FEATURES = ["own_ret", "ma_gap_5", "ma_gap_20", "vol_5"]
# 全資産で共通の外生的特徴量（市場環境）
EXO_FEATURES = [
    "vix_close",
    "vix_chg",
    "fut_ret",
    "fut_gap",
    "usdjpy_ret",
    "dxy_ret",
    "ust10y_chg",
    "curve_spread",
]

# 約80%予測区間に使う係数（正規分布の80%片側点）
_Z80 = 1.2816


@dataclass
class Prediction:
    """予測結果をまとめた構造体。"""
    asset: str                # 対象資産名（表示用）
    pred_return: float        # 予測された翌日リターン（小数, 例 0.004 = +0.4%）
    pred_close: float         # 予測された翌日終値
    last_close: float         # 直近の終値
    pred_low: float           # 翌日終値の予測区間 下限（約80%）
    pred_high: float          # 翌日終値の予測区間 上限（約80%）
    direction: str            # "上昇" / "下落" / "横ばい"
    confidence: str           # "高" / "中" / "低"
    backtest_mae: float       # 検証データでの平均絶対誤差（リターン基準）
    direction_hit: float      # 検証データでの方向的中率（0-1）
    feature_importance: dict  # 特徴量の重要度
    n_train: int              # 学習サンプル数
    # 複数日先の予測（1..H 営業日）: [{"day":1,"close":..,"low":..,"high":..}, ...]
    multiday: list = field(default_factory=list)
    # 的中履歴（検証期間）: 予測終値 vs 実際の終値、方向的中率の推移
    bt_dates: list = field(default_factory=list)
    bt_actual_close: list = field(default_factory=list)
    bt_pred_close: list = field(default_factory=list)
    bt_roll_hit: list = field(default_factory=list)


def _make_features(frame: pd.DataFrame, close_col: str, ret_col: str) -> pd.DataFrame:
    """生の特徴量テーブルからモデル入力用の派生特徴量を作る。"""
    df = frame.copy()
    close = df[close_col]
    df["own_ret"] = df[ret_col]
    df["ma_gap_5"] = close / close.rolling(5).mean() - 1
    df["ma_gap_20"] = close / close.rolling(20).mean() - 1
    df["vol_5"] = df[ret_col].rolling(5).std()

    # 欠けている外生特徴量があれば 0 で埋めて存在を保証
    for col in EXO_FEATURES:
        if col not in df.columns:
            df[col] = 0.0
    return df


def _build_ensemble() -> list:
    """予測に使う複数モデルを生成する（すべて木ベース＝スケーリング不要）。"""
    return [
        GradientBoostingRegressor(
            n_estimators=200, max_depth=3, learning_rate=0.03,
            subsample=0.8, random_state=42,
        ),
        RandomForestRegressor(
            n_estimators=300, max_depth=5, min_samples_leaf=5,
            random_state=42, n_jobs=-1,
        ),
        ExtraTreesRegressor(
            n_estimators=300, max_depth=6, min_samples_leaf=5,
            random_state=42, n_jobs=-1,
        ),
    ]


def predict_asset(
    frame: pd.DataFrame,
    close_col: str = "sp500_close",
    ret_col: str = "sp500_ret",
    asset: str = "S&P500",
    horizon: int = 5,
) -> Prediction | None:
    """指定資産の翌日〜複数日先の予測を行う。

    引数 frame は data.build_feature_frame の出力。
    対象資産の close_col / ret_col を指定して使い回す。
    データが不足している場合は None を返す。
    """
    if frame is None or frame.empty or close_col not in frame.columns:
        return None
    if len(frame) < 60:
        return None

    df = _make_features(frame, close_col, ret_col)
    feat_cols = ASSET_FEATURES + EXO_FEATURES

    # 目的変数: 翌日のリターン（当日特徴量 → 翌日リターン）
    df["target"] = df[ret_col].shift(-1)

    model_df = df[feat_cols + ["target", close_col]].dropna()
    if len(model_df) < 50:
        return None

    X = model_df[feat_cols].values
    y = model_df["target"].values
    closes = model_df[close_col].values
    dates = model_df.index

    # 予測対象は dropna 前の最新行の特徴量
    latest_feat = df[feat_cols].dropna().iloc[[-1]].values
    last_close = float(df[close_col].dropna().iloc[-1])

    # 時系列ホールドアウト: 末尾20%を検証に使う
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    models = _build_ensemble()
    for m in models:
        m.fit(X_train, y_train)

    # 検証（アンサンブル平均）で精度・的中履歴・残差を測る
    bt_dates: list = []
    bt_actual_close: list = []
    bt_pred_close: list = []
    bt_roll_hit: list = []
    resid_std = float("nan")
    backtest_mae = float("nan")
    direction_hit = float("nan")

    if len(X_test) > 0:
        preds_test = np.mean([m.predict(X_test) for m in models], axis=0)
        backtest_mae = float(mean_absolute_error(y_test, preds_test))
        hits = (np.sign(preds_test) == np.sign(y_test)).astype(float)
        direction_hit = float(np.mean(hits))
        resid_std = float(np.std(y_test - preds_test))

        test_closes = closes[split:]          # 特徴量日の終値
        test_dates = dates[split:]
        actual_next = test_closes * (1 + y_test)
        pred_next = test_closes * (1 + preds_test)
        roll = pd.Series(hits).rolling(20, min_periods=5).mean() * 100

        bt_dates = [d.strftime("%Y-%m-%d") for d in test_dates]
        bt_actual_close = actual_next.tolist()
        bt_pred_close = pred_next.tolist()
        bt_roll_hit = roll.tolist()

    if np.isnan(resid_std) or resid_std == 0:
        # フォールバック: 直近リターンのボラティリティ
        resid_std = float(np.nanstd(y[-60:])) or 0.01

    # 全データで再学習してから翌日を予測（精度評価とは分ける）
    final_models = _build_ensemble()
    for m in final_models:
        m.fit(X, y)
    pred_return = float(np.mean([m.predict(latest_feat)[0] for m in final_models]))
    pred_close = last_close * (1 + pred_return)
    pred_low = last_close * (1 + pred_return - _Z80 * resid_std)
    pred_high = last_close * (1 + pred_return + _Z80 * resid_std)

    # 複数日先: 同じ日次ドリフトが続くと仮定し、区間は √h で拡大
    multiday = []
    for h in range(1, horizon + 1):
        cum_ret = pred_return * h
        band = _Z80 * resid_std * np.sqrt(h)
        multiday.append(
            {
                "day": h,
                "close": last_close * (1 + cum_ret),
                "low": last_close * (1 + cum_ret - band),
                "high": last_close * (1 + cum_ret + band),
            }
        )

    # 方向判定（±0.1% 未満は横ばい扱い）
    if pred_return > 0.001:
        direction = "上昇"
    elif pred_return < -0.001:
        direction = "下落"
    else:
        direction = "横ばい"

    # 信頼度: 方向的中率を基準に簡易判定
    if not np.isnan(direction_hit):
        if direction_hit >= 0.58:
            confidence = "高"
        elif direction_hit >= 0.52:
            confidence = "中"
        else:
            confidence = "低"
    else:
        confidence = "低"

    # 特徴量重要度: 木ベースモデルの平均
    imp_arrays = [m.feature_importances_ for m in final_models if hasattr(m, "feature_importances_")]
    mean_imp = np.mean(imp_arrays, axis=0)
    importance = dict(zip(feat_cols, mean_imp.tolist()))

    return Prediction(
        asset=asset,
        pred_return=pred_return,
        pred_close=pred_close,
        last_close=last_close,
        pred_low=pred_low,
        pred_high=pred_high,
        direction=direction,
        confidence=confidence,
        backtest_mae=backtest_mae,
        direction_hit=direction_hit,
        feature_importance=importance,
        n_train=len(X),
        multiday=multiday,
        bt_dates=bt_dates,
        bt_actual_close=bt_actual_close,
        bt_pred_close=bt_pred_close,
        bt_roll_hit=bt_roll_hit,
    )


def predict_next_day(frame: pd.DataFrame) -> Prediction | None:
    """後方互換: S&P500 の翌日予測。"""
    return predict_asset(frame, "sp500_close", "sp500_ret", "S&P500")
