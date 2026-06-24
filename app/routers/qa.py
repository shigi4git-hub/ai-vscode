"""
Q&A ルーター
  POST /qa エンドポイント: 質問を受け取り、RAG パイプラインで回答を生成
  フィードバックループ対応版：prompt_type と loop_count パラメータをサポート
"""

import os
from pathlib import Path
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, status
from dotenv import load_dotenv

from rag.rag_pipeline import rag_with_sources
from app.services.token_logger import generate_request_id, log_feedback_loop

# 環境変数の読み込み
load_dotenv()

# ─────────────────────────────────────────────────────────
# リクエスト・レスポンスモデル
# ─────────────────────────────────────────────────────────
class QARequest(BaseModel):
    """Q&A リクエストのデータモデル"""
    question: str = Field(..., min_length=1, max_length=500, description="ユーザーからの質問")
    prompt_type: str = Field(default="normal", description="使用するプロンプトタイプ: 'normal'（初回）、'retry'（再質問）、未指定で従来動作")
    loop_count: int = Field(default=0, description="フィードバックループの回数（0=初回、1以上=再質問）")


class SourceInfo(BaseModel):
    """引用元情報のデータモデル"""
    source: str = Field(..., description="ソースファイル名（例：test.pdf）")
    page: int | str = Field(..., description="ページ番号")
    content_preview: str = Field(..., description="チャンク内容の冒頭（最初 200 文字）")


class QAResponse(BaseModel):
    """Q&A レスポンスのデータモデル"""
    answer: str = Field(..., description="AI が生成した回答")
    sources: list[SourceInfo] = Field(..., description="参照した引用元チャンクの情報一覧")


# ─────────────────────────────────────────────────────────
# ルーター初期化
# ─────────────────────────────────────────────────────────
router = APIRouter(
    prefix="/qa",
    tags=["qa"],
    responses={404: {"description": "Not found"}},
)


# ─────────────────────────────────────────────────────────
# POST /qa エンドポイント
# ─────────────────────────────────────────────────────────
@router.post("/", response_model=QAResponse)
async def ask_question(request: QARequest) -> dict:
    """
    質問を受け取り、RAG パイプラインで回答を生成して返す。
    フィードバックループ対応：prompt_type により使い分けるプロンプトが変わる。

    Args:
        request: QARequest（質問テキスト、prompt_type、loop_count）

    Returns:
        QAResponse: 回答と引用元情報

    Raises:
        HTTPException: RAG 処理中にエラーが発生した場合
    """
    try:
        # プロジェクトルート（.env がある場所）を基準にパスを設定
        root_dir = Path(__file__).resolve().parent.parent.parent
        
        # prompt_type に応じてプロンプトファイルを決定
        # デフォルト（未指定）は従来どおり qa_prompt_v2.yaml を使用
        if request.prompt_type == "normal":
            # フィードバックループの初回質問用プロンプト
            prompt_yaml_path = root_dir / "prompts" / "feedback_loop" / "normal_prompt.yaml"
        elif request.prompt_type == "retry":
            # フィードバックループの再質問用プロンプト（詳細説明を促す）
            prompt_yaml_path = root_dir / "prompts" / "feedback_loop" / "retry_prompt.yaml"
        else:
            # 未指定時は既存動作を保持（qa_prompt_v2.yaml）
            prompt_yaml_path = root_dir / "prompts" / "qa_prompt_v2.yaml"
        
        # リクエスト ID を生成（ログ用）
        request_id = generate_request_id()
        
        # RAG パイプラインを実行（指定したプロンプトを使用）
        result = rag_with_sources(request.question, k=3, prompt_yaml_path=prompt_yaml_path)

        # レスポンスに source・page・content_preview を含める
        # SourceInfo モデルでバリデーション
        sources = [
            SourceInfo(
                source=source["source"],
                page=source["page"],
                content_preview=source["content_preview"]
            )
            for source in result["sources"]
        ]

        # フィードバックループ対応：ログを記録（初回または再質問のみ）
        # この時点では rating なし（good/bad は別途 /feedback で送信される）
        # ここでは question・answer・prompt_type をログに記録
        if request.prompt_type in ["normal", "retry"]:
            # プロンプトファイルを読み込んでテンプレート部分をログに記録
            try:
                import yaml
                with open(prompt_yaml_path, 'r', encoding='utf-8') as f:
                    prompt_config = yaml.safe_load(f)
                    prompt_template = prompt_config.get("prompt", {}).get("template", "")
            except Exception:
                prompt_template = ""
            
            # トークン数は result に含まれる場合はそれを使用、未含の場合は 0
            input_tokens = result.get("input_tokens", 0)
            output_tokens = result.get("output_tokens", 0)
            
            # rating は None（まだ /feedback で評価されていない）
            log_feedback_loop(
                request_id=request_id,
                question=request.question,
                prompt_type=request.prompt_type,
                prompt_content=prompt_template,
                answer=result["answer"],
                rating="pending",  # 回答時点では評価はまだ
                loop_count=request.loop_count,
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )

        return QAResponse(
            answer=result["answer"],
            sources=sources
        )

    except Exception as e:
        # エラーが発生した場合は 500 を返す
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Q&A 処理中にエラーが発生しました: {str(e)}"
        ) from e
