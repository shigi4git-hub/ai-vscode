# RAG Prompt Evaluation

## 概要
このプロジェクトは、既存の FAISS インデックス（`rag/faiss_index/`）を利用して、
RAG の質問応答プロンプトを評価する構成です。

評価スクリプトは `eval/eval_pipeline.py` で、以下を実行します。
- `qa_prompt_v1.yaml` と `qa_prompt_v2.yaml` の両方で同一 5 問をバッチ評価
- 各回答に対して簡易スコア（正確性・簡潔性・根拠・総合）を計算
- 詳細・サマリー・比較（平均と分散）を CSV 保存

## 実行方法
1. `.env` に `OPENAI_API_KEY` を設定
2. 既存インデックス `rag/faiss_index/index.faiss` が存在することを確認
3. 次を実行

```bash
python eval/eval_pipeline.py
```

## 出力ファイル
`eval/results/` に以下が出力されます。
- `eval_results_<timestamp>.csv` : 質問単位の詳細結果
- `eval_summary_<timestamp>.csv` : プロンプト単位の平均スコア
- `eval_comparison_<timestamp>.csv` : 平均とばらつき（分散）の比較

## 採用版プロンプト
- 採用版: `prompts/qa_prompt_v2.yaml`

## 決定理由
最新評価（`eval_comparison_20260619_090940.csv`）の主要値は次の通りです。
- v1: 平均総合スコア `3.47` / 分散 `0.1156`
- v2: 平均総合スコア `3.65` / 分散 `0.1510`

採用判断のポイント:
- v2 は平均総合スコアが v1 より高く、全体品質が改善
- 特に簡潔性の平均が `2.9 -> 3.5` に向上
- 正確性・根拠は v1 と同等の水準を維持

以上より、回答の簡潔性を改善しつつ品質を維持できる `qa_prompt_v2.yaml` を採用します。
