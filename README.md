# S&P500 投資情報ダッシュボード

S&P500 の推移を時系列表示し、VIX 指数・S&P500 先物・世界の経済ニュースを
組み込んだうえで、翌日の予測値（参考シグナル）を表示する Streamlit アプリです。

## 機能

- 📈 **S&P500 推移**: ローソク足 + 移動平均（MA20/MA50）チャート、毎日更新
- 😱 **VIX 指数**: 恐怖指数の現況と推移
- 🔮 **S&P500 先物 (ES=F)**: 現況と現物との乖離（センチメントの目安）
- 💱 **為替**: USD/JPY・ドル指数（DXY）の現況と推移
- 🏦 **米国債利回り**: 10年債・3ヶ月債と「10年-3ヶ月スプレッド」（逆イールド判定）
- 🏭 **セクター別 ETF**: 11 セクター（XLK/XLF/XLV…）の前日比・期間騰落ランキング
- 🌍 **世界の経済ニュース**: 無料 RSS から主要ヘッドラインを集約
- 🤖 **翌日予測**: VIX・先物・為替・金利・移動平均乖離などを特徴量にした軽量 ML（GradientBoosting）

## セットアップ

```powershell
cd C:\Users\kahoo\Downloads\sp500_app
python -m pip install -r requirements.txt
```

## 起動

```powershell
streamlit run app.py
```

ブラウザが自動で開きます（既定 http://localhost:8501）。
サイドバーの「🔄 データを今すぐ更新」で最新データを再取得できます。

## ファイル構成

| ファイル | 役割 |
|---|---|
| `app.py` | Streamlit UI 本体 |
| `data.py` | yfinance によるデータ取得・特徴量生成 |
| `model.py` | 翌日予測モデル（統計 + 軽量 ML） |
| `news.py` | 経済ニュース RSS 取得 |
| `requirements.txt` | 依存パッケージ |

## ⚠️ 重要な免責事項

- 株価の翌日値を正確に予測することは原理的に不可能です。
- 本アプリの「予測値」は過去データに基づく**参考シグナル**であり、
  将来の値や投資成果を一切保証しません。
- データは yfinance（無料）由来で、遅延・欠損が生じる場合があります。
- 投資判断は必ずご自身の責任で行ってください。本アプリは投資勧誘ではありません。

## データソース

- S&P500: `^GSPC` / VIX: `^VIX` / S&P500 先物: `ES=F`
- 為替: USD/JPY `JPY=X` / ドル指数 `DX-Y.NYB`
- 米国債利回り: 10年 `^TNX` / 3ヶ月 `^IRX`
- セクター ETF: `XLK` `XLF` `XLV` `XLY` `XLP` `XLE` `XLI` `XLU` `XLB` `XLRE` `XLC`
- （すべて Yahoo Finance 経由、APIキー不要）
- ニュース: Yahoo Finance / CNBC / MarketWatch / Investing.com の公開 RSS
