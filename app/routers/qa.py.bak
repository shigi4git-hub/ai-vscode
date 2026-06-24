"""
Q&A ルーター
  POST /qa エンドポイント: 質問を受け取り、RAG パイプラインで回答を生成
"""

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, status

from rag.rag_pipeline import rag_with_sources

# ─────────────────────────────────────────────────────────
# リクエスト・レスポンスモデル
# ─────────────────────────────────────────────────────────
class QARequest(BaseModel):
    """Q&A リクエストのデータモデル"""
    question: str = Field(..., min_length=1, max_length=500, description="ユーザーからの質問")


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

    Args:
        request: QARequest（質問テキスト）

    Returns:
        QAResponse: 回答と引用元情報

    Raises:
        HTTPException: RAG 処理中にエラーが発生した場合
    """
    try:
        # RAG パイプラインを実行
        result = rag_with_sources(request.question, k=3)

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
