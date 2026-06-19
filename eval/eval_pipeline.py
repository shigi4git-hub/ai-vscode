"""
RAG システム評価パイプライン
  テスト質問 5 問に対して qa_prompt_v1 / qa_prompt_v2 を一括評価し、
  詳細結果・サマリー・比較レポートを CSV に保存する。

実行方法:
    python eval/eval_pipeline.py

出力:
    - eval/results/eval_results_<タイムスタンプ>.csv
    - eval/results/eval_summary_<タイムスタンプ>.csv
    - eval/results/eval_comparison_<タイムスタンプ>.csv
"""

import csv
import os
import sys
from datetime import datetime
from pathlib import Path
from statistics import mean, pvariance

import yaml
from dotenv import load_dotenv

# プロジェクトルートをパスに追加（rag モジュールをインポート可能にする）
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from rag.rag_pipeline import rag_with_sources

# ─────────────────────────────────────────────────────────
# 環境変数の読み込み
# ─────────────────────────────────────────────────────────
load_dotenv(ROOT_DIR / ".env")

# ─────────────────────────────────────────────────────────
# 定数
# ─────────────────────────────────────────────────────────
TEST_QUESTIONS_YAML = ROOT_DIR / "prompts" / "test_questions.yaml"
EVAL_CRITERIA_YAML = ROOT_DIR / "prompts" / "evaluation_criteria.yaml"
RESULTS_DIR = ROOT_DIR / "eval" / "results"
INDEX_DIR = ROOT_DIR / "rag" / "faiss_index"
MAX_TEST_QUESTIONS = 5

# 比較対象のプロンプト定義
# v1: 基本版、v2: 簡潔性強化版（1〜3文）、v3: 厳密簡潔版（必ず2文）
PROMPT_VARIANTS = {
    "v1": ROOT_DIR / "prompts" / "qa_prompt_v1.yaml",
    "v2": ROOT_DIR / "prompts" / "qa_prompt_v2.yaml",
    "v3": ROOT_DIR / "prompts" / "qa_prompt_v3.yaml",
}


# ─────────────────────────────────────────────────────────
# 事前チェック
# ─────────────────────────────────────────────────────────
def validate_runtime_requirements() -> None:
    """
    実行に必要な前提条件を確認する。
    - .env 由来の OPENAI_API_KEY が設定されていること
    - 既存の FAISS インデックスが存在すること
    - 比較対象のプロンプト YAML が存在すること
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("[ERROR] OPENAI_API_KEY が設定されていません。")
        print("  .env に OPENAI_API_KEY を設定して再実行してください。")
        sys.exit(1)

    index_file = INDEX_DIR / "index.faiss"
    if not index_file.exists():
        print(f"[ERROR] 既存の FAISS インデックスが見つかりません: {index_file}")
        print("  先に rag/faiss_index/ を作成してから再実行してください。")
        sys.exit(1)

    for version, prompt_path in PROMPT_VARIANTS.items():
        if not prompt_path.exists():
            print(f"[ERROR] プロンプト YAML が見つかりません ({version}): {prompt_path}")
            sys.exit(1)


# ─────────────────────────────────────────────────────────
# YAML ファイル読み込み関数
# ─────────────────────────────────────────────────────────
def load_test_questions(yaml_path: Path) -> list:
    """
    YAML ファイルからテスト質問を読み込んで返す。
    テスト質問は [question, id, category, difficulty] の辞書リストに変換する。
    """
    if not yaml_path.exists():
        print(f"[ERROR] テスト質問 YAML が見つかりません: {yaml_path}")
        sys.exit(1)

    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        test_qs = config.get("test_questions", {})
        questions_list = []

        # question_01, question_02 ... の順に処理する
        for key in sorted(test_qs.keys()):
            q_data = test_qs[key]
            questions_list.append(
                {
                    "id": q_data.get("id"),
                    "question": q_data.get("question"),
                    "category": q_data.get("category"),
                    "difficulty": q_data.get("difficulty"),
                }
            )

        return questions_list
    except Exception as e:
        print(f"[ERROR] テスト質問 YAML 読み込み失敗: {e}")
        sys.exit(1)


def load_evaluation_criteria(yaml_path: Path) -> dict:
    """
    YAML ファイルから評価観点を読み込んで返す。
    現在は集計表示用に読み込むのみで、スコア計算本体には未使用。
    """
    if not yaml_path.exists():
        print(f"[WARNING] 評価観点 YAML が見つかりません: {yaml_path}")
        return None

    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return config.get("evaluation_criteria", {})
    except Exception as e:
        print(f"[WARNING] 評価観点 YAML 読み込み失敗: {e}")
        return None


# ─────────────────────────────────────────────────────────
# RAG パイプライン実行・結果取得
# ─────────────────────────────────────────────────────────
def run_rag_evaluation(question: str, question_id: str, prompt_version: str, prompt_yaml: Path) -> dict:
    """
    質問に対して RAG パイプラインを実行し、結果を返す。

    Args:
        question: テスト質問
        question_id: 質問 ID
        prompt_version: 評価対象プロンプトのバージョン（v1/v2）
        prompt_yaml: 使用するプロンプト YAML パス

    Returns:
        評価用の 1 レコード分の辞書
    """
    try:
        # 既存の FAISS インデックスを使い、指定バージョンのプロンプトで回答生成
        result = rag_with_sources(question, k=3, prompt_yaml_path=prompt_yaml)

        answer = result.get("answer", "")
        sources = result.get("sources", [])

        # ソース情報を抽出
        source_files = ",".join([s.get("source", "") for s in sources])
        source_pages = ",".join([str(s.get("page", "")) for s in sources])

        return {
            "prompt_version": prompt_version,
            "prompt_file": prompt_yaml.name,
            "question_id": question_id,
            "question": question,
            "answer": answer,
            "num_sources": len(sources),
            "source_files": source_files,
            "source_pages": source_pages,
            "error": None,
        }
    except Exception as e:
        # エラーが発生した場合も比較可能な形式で返す
        return {
            "prompt_version": prompt_version,
            "prompt_file": prompt_yaml.name,
            "question_id": question_id,
            "question": question,
            "answer": "",
            "num_sources": 0,
            "source_files": "",
            "source_pages": "",
            "error": str(e),
        }


# ─────────────────────────────────────────────────────────
# 評価スコア計算（簡易版）
# ─────────────────────────────────────────────────────────
def calculate_evaluation_score(answer: str) -> dict:
    """
    生成された回答に対して簡易的な評価スコアを計算する。
    実運用では、LLMを使った詳細な評価が推奨される。

    Args:
        answer: 生成された回答テキスト

    Returns:
        {
            "accuracy_score": 3.5,
            "conciseness_score": 3.0,
            "evidence_score": 3.5,
            "overall_score": 3.3
        }
    """
    # 回答の長さで簡潔性を評価
    answer_length = len(answer)
    if answer_length < 50:
        conciseness_score = 2.0
    elif answer_length < 200:
        conciseness_score = 4.5
    elif answer_length < 500:
        conciseness_score = 4.0
    else:
        conciseness_score = 2.5

    # 根拠の提示をキーワードで簡易チェック
    evidence_keywords = ["コンテキスト", "記載", "ドキュメント", "ページ", "わかりません"]
    has_evidence = any(keyword in answer for keyword in evidence_keywords)
    evidence_score = 4.0 if has_evidence else 2.5

    # 不明時に断る回答かどうかと、回答量を簡易評価
    if "わかりません" in answer or "記載されていません" in answer or "不明" in answer:
        accuracy_score = 3.5
    elif answer_length > 100:
        accuracy_score = 4.0
    else:
        accuracy_score = 3.0

    # 総合スコア（重み付き平均）
    overall_score = (
        accuracy_score * 0.4
        + conciseness_score * 0.3
        + evidence_score * 0.3
    )

    return {
        "accuracy_score": round(accuracy_score, 2),
        "conciseness_score": round(conciseness_score, 2),
        "evidence_score": round(evidence_score, 2),
        "overall_score": round(overall_score, 2),
    }


def _safe_metric_values(results: list, metric_key: str) -> list:
    """
    指定メトリクスの値を安全に抽出する。
    エラー行や欠損値を除外して、統計計算用の数値配列を返す。
    """
    values = []
    for result in results:
        if result.get("error"):
            continue
        value = result.get(metric_key)
        if isinstance(value, (int, float)):
            values.append(float(value))
    return values


def compute_prompt_statistics(results: list, prompt_version: str) -> dict:
    """
    指定プロンプトバージョンの結果から平均・分散を計算する。

    Returns:
        比較レポート 1 行分の辞書
    """
    prompt_results = [r for r in results if r.get("prompt_version") == prompt_version]
    success_results = [r for r in prompt_results if not r.get("error")]

    def metric_summary(metric_key: str) -> tuple:
        metric_values = _safe_metric_values(prompt_results, metric_key)
        if not metric_values:
            return 0.0, 0.0
        return mean(metric_values), pvariance(metric_values)

    avg_accuracy, var_accuracy = metric_summary("accuracy_score")
    avg_conciseness, var_conciseness = metric_summary("conciseness_score")
    avg_evidence, var_evidence = metric_summary("evidence_score")
    avg_overall, var_overall = metric_summary("overall_score")

    return {
        "Prompt_Version": prompt_version,
        "Prompt_File": PROMPT_VARIANTS[prompt_version].name,
        "Total_Questions": len(prompt_results),
        "Successful": len(success_results),
        "Failed": len(prompt_results) - len(success_results),
        "Avg_Accuracy_Score": round(avg_accuracy, 4),
        "Var_Accuracy_Score": round(var_accuracy, 4),
        "Avg_Conciseness_Score": round(avg_conciseness, 4),
        "Var_Conciseness_Score": round(var_conciseness, 4),
        "Avg_Evidence_Score": round(avg_evidence, 4),
        "Var_Evidence_Score": round(var_evidence, 4),
        "Avg_Overall_Score": round(avg_overall, 4),
        "Var_Overall_Score": round(var_overall, 4),
    }


# ─────────────────────────────────────────────────────────
# CSV ファイル保存
# ─────────────────────────────────────────────────────────
def save_results_to_csv(results: list, timestamp: str) -> tuple:
    """
    評価結果を CSV ファイルに保存する。

    1. 詳細結果 CSV（質問 x プロンプト）
    2. サマリー CSV（各プロンプトの平均値）
    3. 比較 CSV（平均 + ばらつき）

    Args:
        results: 評価結果のリスト
        timestamp: タイムスタンプ文字列

    Returns:
        (詳細結果ファイルパス, サマリーファイルパス, 比較ファイルパス)
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    detail_file = RESULTS_DIR / f"eval_results_{timestamp}.csv"
    summary_file = RESULTS_DIR / f"eval_summary_{timestamp}.csv"
    comparison_file = RESULTS_DIR / f"eval_comparison_{timestamp}.csv"

    # 1) 詳細結果
    detail_headers = [
        "Prompt_Version",
        "Prompt_File",
        "Question_ID",
        "Question",
        "Category",
        "Difficulty",
        "Answer",
        "Num_Sources",
        "Source_Files",
        "Source_Pages",
        "Accuracy_Score",
        "Conciseness_Score",
        "Evidence_Score",
        "Overall_Score",
        "Error",
    ]

    with open(detail_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=detail_headers)
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "Prompt_Version": result["prompt_version"],
                    "Prompt_File": result["prompt_file"],
                    "Question_ID": result["question_id"],
                    "Question": result["question"],
                    "Category": result.get("category", ""),
                    "Difficulty": result.get("difficulty", ""),
                    "Answer": result["answer"],
                    "Num_Sources": result["num_sources"],
                    "Source_Files": result["source_files"],
                    "Source_Pages": result["source_pages"],
                    "Accuracy_Score": result.get("accuracy_score", ""),
                    "Conciseness_Score": result.get("conciseness_score", ""),
                    "Evidence_Score": result.get("evidence_score", ""),
                    "Overall_Score": result.get("overall_score", ""),
                    "Error": result["error"] or "",
                }
            )

    print(f"\n✓ 詳細結果を保存: {detail_file}")

    # 2) サマリー結果（各プロンプトの平均）
    summary_headers = [
        "Prompt_Version",
        "Prompt_File",
        "Total_Questions",
        "Successful",
        "Failed",
        "Avg_Accuracy_Score",
        "Avg_Conciseness_Score",
        "Avg_Evidence_Score",
        "Avg_Overall_Score",
    ]

    summary_rows = []
    for version in PROMPT_VARIANTS.keys():
        stats_row = compute_prompt_statistics(results, version)
        summary_rows.append(
            {
                "Prompt_Version": stats_row["Prompt_Version"],
                "Prompt_File": stats_row["Prompt_File"],
                "Total_Questions": stats_row["Total_Questions"],
                "Successful": stats_row["Successful"],
                "Failed": stats_row["Failed"],
                "Avg_Accuracy_Score": f"{stats_row['Avg_Accuracy_Score']:.4f}",
                "Avg_Conciseness_Score": f"{stats_row['Avg_Conciseness_Score']:.4f}",
                "Avg_Evidence_Score": f"{stats_row['Avg_Evidence_Score']:.4f}",
                "Avg_Overall_Score": f"{stats_row['Avg_Overall_Score']:.4f}",
            }
        )

    with open(summary_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=summary_headers)
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"✓ サマリー結果を保存: {summary_file}")

    # 3) 比較結果（平均 + ばらつき）
    comparison_headers = [
        "Prompt_Version",
        "Prompt_File",
        "Total_Questions",
        "Successful",
        "Failed",
        "Avg_Accuracy_Score",
        "Var_Accuracy_Score",
        "Avg_Conciseness_Score",
        "Var_Conciseness_Score",
        "Avg_Evidence_Score",
        "Var_Evidence_Score",
        "Avg_Overall_Score",
        "Var_Overall_Score",
    ]

    comparison_rows = [compute_prompt_statistics(results, version) for version in PROMPT_VARIANTS.keys()]

    with open(comparison_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=comparison_headers)
        writer.writeheader()
        writer.writerows(comparison_rows)

    print(f"✓ 比較レポートを保存: {comparison_file}")

    return detail_file, summary_file, comparison_file


# ─────────────────────────────────────────────────────────
# メイン処理
# ─────────────────────────────────────────────────────────
def main() -> None:
    """
    評価パイプラインのメイン処理：
    1. 実行前チェック（APIキー、FAISS、プロンプト）
    2. テスト質問 5 問を読み込み
    3. qa_prompt_v1 / qa_prompt_v2 でバッチ実行
    4. 各回答をスコアリング
    5. 詳細・サマリー・比較 CSV を保存
    """
    print("=" * 70)
    print("  RAG システム評価パイプライン開始（v1/v2/v3 比較）")
    print("=" * 70)

    # ステップ 0: 実行前チェック
    print("\n[STEP 0] 実行前チェック...")
    validate_runtime_requirements()
    print("  ✓ OPENAI_API_KEY / FAISS / プロンプト YAML を確認")

    # ステップ 1: テスト質問を読み込む（先頭 5 問）
    print("\n[STEP 1] テスト質問の読み込み...")
    all_test_questions = load_test_questions(TEST_QUESTIONS_YAML)
    test_questions = all_test_questions[:MAX_TEST_QUESTIONS]
    print(f"  ✓ {len(test_questions)} 件のテスト質問を使用（先頭 {MAX_TEST_QUESTIONS} 問）")

    # ステップ 2: 評価観点を読み込む（オプション）
    print("\n[STEP 2] 評価観点の読み込み...")
    eval_criteria = load_evaluation_criteria(EVAL_CRITERIA_YAML)
    if eval_criteria:
        print("  ✓ 評価観点を読み込み")
    else:
        print("  ⚠ 評価観点の読み込みをスキップ（簡易評価を使用）")

    # ステップ 3: v1 / v2 / v3 で回答生成 + スコアリング
    print("\n[STEP 3] プロンプト v1 / v2 / v3 でバッチ評価...")
    results = []

    for version, prompt_path in PROMPT_VARIANTS.items():
        print(f"\n  [PROMPT {version}] {prompt_path.name}")
        for i, q_data in enumerate(test_questions, start=1):
            print(f"    - [{i}/{len(test_questions)}] {q_data['id']}: {q_data['question'][:50]}...")

            rag_result = run_rag_evaluation(
                question=q_data["question"],
                question_id=q_data["id"],
                prompt_version=version,
                prompt_yaml=prompt_path,
            )

            # 質問メタデータを結果に付与
            rag_result["category"] = q_data.get("category", "")
            rag_result["difficulty"] = q_data.get("difficulty", "")

            if not rag_result["error"]:
                scores = calculate_evaluation_score(rag_result["answer"])
                rag_result.update(scores)
                print(
                    f"      回答長: {len(rag_result['answer'])} 文字, "
                    f"ソース数: {rag_result['num_sources']}, "
                    f"総合スコア: {rag_result['overall_score']}"
                )
            else:
                print(f"      エラー: {rag_result['error']}")

            results.append(rag_result)

    # ステップ 4: CSV 保存
    print("\n[STEP 4] 結果を CSV に保存...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    detail_file, summary_file, comparison_file = save_results_to_csv(results, timestamp)

    # ステップ 5: コンソールサマリー表示
    print("\n" + "=" * 70)
    print("  評価結果サマリー（v1/v2/v3 比較）")
    print("=" * 70)

    for version in PROMPT_VARIANTS.keys():
        stats = compute_prompt_statistics(results, version)
        success_rate = (
            (stats["Successful"] / stats["Total_Questions"] * 100)
            if stats["Total_Questions"] > 0
            else 0.0
        )

        print(f"\n  [{version}] {stats['Prompt_File']}")
        print(f"    - 成功/失敗: {stats['Successful']}/{stats['Failed']} (成功率 {success_rate:.1f}%)")
        print(
            f"    - 平均総合スコア: {stats['Avg_Overall_Score']:.4f} "
            f"(分散 {stats['Var_Overall_Score']:.4f})"
        )

    print(f"\n  詳細結果: {detail_file.name}")
    print(f"  サマリー結果: {summary_file.name}")
    print(f"  比較レポート: {comparison_file.name}")


if __name__ == "__main__":
    main()
