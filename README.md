# FIREを目指そう by よしけい

S&P500を中心に、主要インデックス・市場環境・翌日予測・金利株価ニュースを
1画面で確認できるインデックス投資の参考ダッシュボード（Streamlit製）。

- 公開URL: https://yoshikei-invest-app-ver1.streamlit.app
- 開発記録・復旧手順: [開発記録.md](開発記録.md)

## 機能

- 📊 **現況カード**: S&P500 / S&P500先物 / 先物-現物乖離 / NASDAQ100 / SCHD / オルカン / VIX（前日比つき）
- 💱 **為替・金利**: USD/JPY・ドル指数(DXY)・米国10年債・利回り差(10年-3ヶ月)
- 📈 **Index chart**: S&P500 / NASDAQ100 / SCHD / オルカン のローソク足＋移動平均＋翌日予測
- 🔮 **予測（参考シグナル）**: アンサンブルML、予測区間、複数日予測、的中履歴、特徴量重要度
- 🏢 **Index 構成概要**: 各ファンドの組入上位銘柄＋業種構成比率
- 🏭 **業種別 パフォーマンス**: 11業種ETFの前日比・期間騰落ランキング
- 🛡️ **資金逃避先**: ディフェンシブ資産の対S&P500相対パフォーマンス
- 📰 **金利・株価ニュース**: NHK・Yahoo!ニュース（日本語）＋米国Yahoo Finance（英語＋日本語訳）

## セットアップ・起動

```powershell
cd C:\Users\kahoo\Downloads\sp500_app
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## ファイル構成

| ファイル | 役割 |
|---|---|
| `app.py` | Streamlit UI 本体 |
| `data.py` | yfinance データ取得・特徴量生成・ファンド構成 |
| `model.py` | 翌日〜複数日予測モデル（アンサンブルML） |
| `news.py` | 金利・株価ニュース RSS 取得 |
| `requirements.txt` | 依存パッケージ |

## ⚠️ 重要な免責事項

- 株価の翌日値を正確に予測することは原理的に不可能です。
- 「予測値」は過去データに基づく**参考シグナル**であり、将来の値や投資成果を一切保証しません。
- データは yfinance（無料）由来で、遅延・欠損が生じる場合があります。
- 投資判断は必ずご自身の責任で行ってください。本アプリは投資勧誘ではありません。

## データソース

- 指数: S&P500 `^GSPC` / VIX `^VIX` / 先物 `ES=F` / NASDAQ `QQQ` / SCHD `SCHD` / 全世界 `ACWI`
- 為替: USD/JPY `JPY=X` / ドル指数 `DX-Y.NYB`
- 金利: 10年 `^TNX` / 3ヶ月 `^IRX`
- 業種ETF: `XLK` `XLF` `XLV` `XLY` `XLP` `XLE` `XLI` `XLU` `XLB` `XLRE` `XLC`
- ニュース: NHK・Yahoo!ニュース・米国Yahoo Finance の公開 RSS
- （すべて無料、APIキー不要）
