"""
RAG システム評価パイプライン
  テスト質問セットを実行し、RAG システムの回答を生成・評価してCSVに保存
  
実行方法:
    python eval/eval_pipeline.py

出力:
    - eval/results/eval_results_<タイムスタンプ>.csv
    - eval/results/eval_summary_<タイムスタンプ>.csv
"""

import csv
import sys
from datetime import datetime
from pathlib import Path

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


# ─────────────────────────────────────────────────────────
# YAML ファイル読み込み関数
# ─────────────────────────────────────────────────────────
def load_test_questions(yaml_path: Path) -> list:
    """
    YAML ファイルからテスト質問を読み込んで返す。
    テスト質問は [question, id, category, difficulty] のリストに変換
    """
    if not yaml_path.exists():
        print(f"[ERROR] テスト質問 YAML が見つかりません: {yaml_path}")
        sys.exit(1)
    
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        test_qs = config.get("test_questions", {})
        questions_list = []
        
        # 各質問を抽出（question_01, question_02, ... の形式）
        for key in sorted(test_qs.keys()):
            q_data = test_qs[key]
            questions_list.append({
                "id": q_data.get("id"),
                "question": q_data.get("question"),
                "category": q_data.get("category"),
                "difficulty": q_data.get("difficulty")
            })
        
        return questions_list
    except Exception as e:
        print(f"[ERROR] テスト質問 YAML 読み込み失敗: {e}")
        sys.exit(1)


def load_evaluation_criteria(yaml_path: Path) -> dict:
    """
    YAML ファイルから評価観点を読み込んで返す。
    """
    if not yaml_path.exists():
        print(f"[WARNING] 評価観点 YAML が見つかりません: {yaml_path}")
        return None
    
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config.get("evaluation_criteria", {})
    except Exception as e:
        print(f"[WARNING] 評価観点 YAML 読み込み失敗: {e}")
        return None


# ─────────────────────────────────────────────────────────
# RAG パイプライン実行・結果取得
# ─────────────────────────────────────────────────────────
def run_rag_evaluation(question: str, question_id: str) -> dict:
    """
    質問に対して RAG パイプラインを実行し、結果を返す。
    
    Args:
        question: テスト質問
        question_id: 質問 ID
    
    Returns:
        {
            "question_id": "Q001",
            "question": "質問テキスト",
            "answer": "生成された回答",
            "num_sources": 3,
            "source_files": "ファイル名,ファイル名,...",
            "source_pages": "1,2,3,...",
            "error": None または エラーメッセージ
        }
    """
    try:
        # RAG パイプラインで回答生成
        result = rag_with_sources(question, k=3)
        
        answer = result.get("answer", "")
        sources = result.get("sources", [])
        
        # ソース情報を抽出
        source_files = ",".join([s.get("source", "") for s in sources])
        source_pages = ",".join([str(s.get("page", "")) for s in sources])
        
        return {
            "question_id": question_id,
            "question": question,
            "answer": answer,
            "num_sources": len(sources),
            "source_files": source_files,
            "source_pages": source_pages,
            "error": None
        }
    except Exception as e:
        # エラーが発生した場合
        return {
            "question_id": question_id,
            "question": question,
            "answer": "",
            "num_sources": 0,
            "source_files": "",
            "source_pages": "",
            "error": str(e)
        }


# ─────────────────────────────────────────────────────────
# 評価スコア計算（簡易版）
# ─────────────────────────────────────────────────────────
def calculate_evaluation_score(answer: str) -> dict:
    """
    生成された回答に対して簡易的な評価スコアを計算する。
    実運用では、LLMを使った詳細な評価が推奨されます。
    
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
    # 簡易的なスコア計算ロジック
    # （実際にはより詳細な分析が必要）
    
    # 回答の長さで簡潔性を評価
    answer_length = len(answer)
    if answer_length < 50:
        conciseness_score = 2.0  # 短すぎる
    elif answer_length < 200:
        conciseness_score = 4.5  # 適切
    elif answer_length < 500:
        conciseness_score = 4.0  # やや長い
    else:
        conciseness_score = 2.5  # 長すぎる
    
    # 根拠の提示をチェック
    evidence_keywords = ["コンテキスト", "記載", "ドキュメント", "ページ", "わかりません"]
    has_evidence = any(keyword in answer for keyword in evidence_keywords)
    evidence_score = 4.0 if has_evidence else 2.5
    
    # 「わかりません」などの回答適切性
    if "わかりません" in answer or "記載されていません" in answer or "不明" in answer:
        accuracy_score = 3.5  # 謙虚で適切
    elif answer_length > 100:
        accuracy_score = 4.0  # 詳細な回答
    else:
        accuracy_score = 3.0  # 基本的な回答
    
    # 総合スコア（重み付け平均）
    overall_score = (
        accuracy_score * 0.4 +
        conciseness_score * 0.3 +
        evidence_score * 0.3
    )
    
    return {
        "accuracy_score": round(accuracy_score, 2),
        "conciseness_score": round(conciseness_score, 2),
        "evidence_score": round(evidence_score, 2),
        "overall_score": round(overall_score, 2)
    }


# ─────────────────────────────────────────────────────────
# CSV ファイル保存
# ─────────────────────────────────────────────────────────
def save_results_to_csv(results: list, timestamp: str) -> tuple:
    """
    評価結果を CSV ファイルに保存する。
    詳細結果と集計結果の2つのファイルを作成。
    
    Args:
        results: 評価結果のリスト
        timestamp: タイムスタンプ文字列
    
    Returns:
        (詳細結果ファイルパス, 集計結果ファイルパス)
    """
    # 出力ディレクトリを作成
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # ファイルパス
    detail_file = RESULTS_DIR / f"eval_results_{timestamp}.csv"
    summary_file = RESULTS_DIR / f"eval_summary_{timestamp}.csv"
    
    # ─────────────────────────────────────────────────────────
    # 1. 詳細結果 CSV を保存
    # ─────────────────────────────────────────────────────────
    detail_headers = [
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
        "Error"
    ]
    
    with open(detail_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=detail_headers)
        writer.writeheader()
        for result in results:
            writer.writerow({
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
                "Error": result["error"] or ""
            })
    
    print(f"\n✓ 詳細結果を保存: {detail_file}")
    
    # ─────────────────────────────────────────────────────────
    # 2. 集計結果 CSV を保存
    # ─────────────────────────────────────────────────────────
    total_count = len(results)
    error_count = sum(1 for r in results if r["error"])
    success_count = total_count - error_count
    
    # 各メトリクスの平均値を計算
    valid_results = [r for r in results if not r["error"]]
    
    if valid_results:
        avg_accuracy = sum(r.get("accuracy_score", 0) for r in valid_results) / len(valid_results)
        avg_conciseness = sum(r.get("conciseness_score", 0) for r in valid_results) / len(valid_results)
        avg_evidence = sum(r.get("evidence_score", 0) for r in valid_results) / len(valid_results)
        avg_overall = sum(r.get("overall_score", 0) for r in valid_results) / len(valid_results)
    else:
        avg_accuracy = avg_conciseness = avg_evidence = avg_overall = 0.0
    
    summary_data = [
        ["Evaluation Summary", ""],
        ["Timestamp", timestamp],
        ["Total_Questions", total_count],
        ["Successful", success_count],
        ["Failed", error_count],
        ["Success_Rate", f"{success_count / total_count * 100:.1f}%" if total_count > 0 else "N/A"],
        ["", ""],
        ["Average Scores", ""],
        ["Avg_Accuracy_Score", f"{avg_accuracy:.2f}"],
        ["Avg_Conciseness_Score", f"{avg_conciseness:.2f}"],
        ["Avg_Evidence_Score", f"{avg_evidence:.2f}"],
        ["Avg_Overall_Score", f"{avg_overall:.2f}"],
    ]
    
    with open(summary_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(summary_data)
    
    print(f"✓ 集計結果を保存: {summary_file}")
    
    return detail_file, summary_file


# ─────────────────────────────────────────────────────────
# メイン処理
# ─────────────────────────────────────────────────────────
def main() -> None:
    """
    評価パイプラインのメイン処理：
    1. テスト質問を読み込む
    2. 各質問に対して RAG で回答生成
    3. 回答を評価
    4. 結果を CSV に保存
    """
    print("=" * 70)
    print("  RAG システム評価パイプライン開始")
    print("=" * 70)
    
    # ステップ 1: テスト質問を読み込む
    print("\n[STEP 1] テスト質問の読み込み...")
    test_questions = load_test_questions(TEST_QUESTIONS_YAML)
    print(f"  ✓ {len(test_questions)} 件のテスト質問を読み込み")
    
    # ステップ 2: 評価観点を読み込む（オプション）
    print("\n[STEP 2] 評価観点の読み込み...")
    eval_criteria = load_evaluation_criteria(EVAL_CRITERIA_YAML)
    if eval_criteria:
        print(f"  ✓ 評価観点を読み込み")
    else:
        print(f"  ⚠ 評価観点の読み込みをスキップ（簡易評価を使用）")
    
    # ステップ 3: 各質問に対して RAG で回答生成
    print("\n[STEP 3] RAG パイプラインで回答生成...")
    results = []
    for i, q_data in enumerate(test_questions, start=1):
        print(f"\n  [{i}/{len(test_questions)}] {q_data['id']}: {q_data['question'][:50]}...")
        
        # RAG で回答生成
        rag_result = run_rag_evaluation(q_data["question"], q_data["id"])
        
        # 結果に質問のメタデータを追加
        rag_result["category"] = q_data.get("category", "")
        rag_result["difficulty"] = q_data.get("difficulty", "")
        
        # 評価スコアを計算
        if not rag_result["error"]:
            scores = calculate_evaluation_score(rag_result["answer"])
            rag_result.update(scores)
            
            print(f"    - 回答長: {len(rag_result['answer'])} 文字")
            print(f"    - ソース数: {rag_result['num_sources']}")
            print(f"    - 総合スコア: {rag_result['overall_score']}")
        else:
            print(f"    - エラー: {rag_result['error']}")
        
        results.append(rag_result)
    
    # ステップ 4: 結果を CSV に保存
    print("\n[STEP 4] 結果を CSV に保存...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    detail_file, summary_file = save_results_to_csv(results, timestamp)
    
    # ステップ 5: 集計結果を表示
    print("\n" + "=" * 70)
    print("  評価結果サマリー")
    print("=" * 70)
    
    total_count = len(results)
    error_count = sum(1 for r in results if r["error"])
    success_count = total_count - error_count
    
    print(f"\n  総質問数: {total_count}")
    print(f"  成功: {success_count}")
    print(f"  失敗: {error_count}")
    print(f"  成功率: {success_count / total_count * 100:.1f}%" if total_count > 0 else "N/A")
    
    valid_results = [r for r in results if not r["error"]]
    if valid_results:
        avg_accuracy = sum(r.get("accuracy_score", 0) for r in valid_results) / len(valid_results)
        avg_conciseness = sum(r.get("conciseness_score", 0) for r in valid_results) / len(valid_results)
        avg_evidence = sum(r.get("evidence_score", 0) for r in valid_results) / len(valid_results)
        avg_overall = sum(r.get("overall_score", 0) for r in valid_results) / len(valid_results)
        
        print(f"\n  平均スコア:")
        print(f"    - 正確性: {avg_accuracy:.2f} / 5.0")
        print(f"    - 簡潔性: {avg_conciseness:.2f} / 5.0")
        print(f"    - 根拠: {avg_evidence:.2f} / 5.0")
        print(f"    - 総合: {avg_overall:.2f} / 5.0")
    
    print(f"\n  📊  詳細結果: {detail_file.name}")
    print(f"  📊 集計結果: {summary_file.name}")
    
    print("\n" + "=" * 70)
    print("  評価パイプライン完了")
    print("=" * 70)


if __name__ == "__main__":
    main()
