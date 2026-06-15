import asyncio
import json
import logging
import os

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from openai import OpenAI

from database import Session
from models.item import Item
from models.user import User
from app.dependencies import get_current_user
from app.services.summarize import summarize_text

# .env ファイルから環境変数を読み込む
load_dotenv()

# モジュールレベルのロガー設定
logger = logging.getLogger(__name__)

# OpenAI クライアントを初期化（APIキーを .env から取得）
_api_key = os.getenv("OPENAI_API_KEY")
_openai_client: OpenAI | None = OpenAI(api_key=_api_key) if _api_key else None

router = APIRouter(prefix="/items", tags=["items"])


class ItemCreate(BaseModel):
    """アイテム作成リクエスト用の入力モデル。"""
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)


def _save_summary(item_id: int, body: str) -> None:
    """
    BackgroundTasks から呼び出される要約保存関数。
    要約が成功した場合は DB の summary カラムを更新する。
    失敗した場合は summary を None のままにして投稿自体には影響を与えない。

    Parameters
    ----------
    item_id : int
        要約を保存する対象アイテムの ID。
    body : str
        要約対象の本文テキスト。
    """
    # 要約を生成する（失敗時は None が返る）
    summary = summarize_text(body)

    # 要約が取得できた場合のみ DB を更新する
    if summary is not None:
        db = Session()
        try:
            item = db.query(Item).filter(Item.id == item_id).first()
            if item:
                item.summary = summary
                db.commit()
        finally:
            db.close()


@router.get("")
def read_items():
    """登録済みアイテム一覧を取得する。"""
    db = Session()
    try:
        items = db.query(Item).order_by(Item.id).all()
        return [
            {
                "id": item.id,
                "title": item.title,
                "body": item.body,
                # summary は非同期で後から書き込まれるため、取得タイミングによっては None の場合がある
                "summary": item.summary,
            }
            for item in items
        ]
    finally:
        db.close()


@router.post("")
def create_item(
    item: ItemCreate,
    background_tasks: BackgroundTasks,  # FastAPI が自動でインジェクトする
    current_user: User = Depends(get_current_user),
):
    """認証済みユーザーが新しいアイテムを作成する。
    投稿完了後、BackgroundTasks で本文の要約を非同期生成・保存する。
    """
    db = Session()
    try:
        # summary は初期値 None で保存し、後でバックグラウンドタスクが更新する
        db_item = Item(title=item.title, body=item.body, summary=None)
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
    finally:
        db.close()

    # レスポンスを返した後にバックグラウンドで要約処理を実行する
    # 要約が失敗しても投稿レスポンスには影響しない
    background_tasks.add_task(_save_summary, db_item.id, item.body)

    return JSONResponse(
        status_code=201,
        content={
            "message": "Item created",
            "item": {
                "id": db_item.id,
                "title": db_item.title,
                "body": db_item.body,
                # 作成直後は要約未生成のため None を返す
                "summary": db_item.summary,
            },
        },
    )


@router.get("/stream")
async def stream_item_analysis(item_id: int):
    """
    指定されたアイテムの本文を OpenAI API でストリーミング処理して返す。
    SSE (Server-Sent Events) 形式でレスポンスを逐次配信。
    
    Parameters
    ----------
    item_id : int
        ストリーミング対象のアイテムID。
    
    Returns
    -------
    StreamingResponse
        SSE 形式でストリーミングされたテキスト。
        エラーの場合は error イベントを送信。
    """
    # OpenAI API キーが未設定の場合は 400 エラーを返す
    if _openai_client is None:
        logger.error("OPENAI_API_KEY が設定されていません")
        raise HTTPException(
            status_code=400,
            detail="OpenAI API key is not configured"
        )
    
    # DB からアイテムを取得
    db = Session()
    try:
        item = db.query(Item).filter(Item.id == item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail=f"Item {item_id} not found")
        # 本文をローカル変数に保存して DB クローズ後に使用
        item_body = item.body
        item_title = item.title
    finally:
        db.close()
    
    async def generate_stream():
        """
        OpenAI API のストリーミングレスポンスを逐次生成するジェネレーター。
        各チャンクを SSE 形式で送信する。
        """
        try:
            # OpenAI Chat Completions API をストリーミングモードで呼び出し
            stream = _openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "あなたは与えられたテキストを分析して、"
                            "その内容について詳しく説明するアシスタントです。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"次のテキストを詳しく分析してください：\n\n"
                            f"【タイトル】{item_title}\n"
                            f"【本文】{item_body}"
                        ),
                    },
                ],
                max_tokens=1000,
                temperature=0.7,
                # stream=True でストリーミング形式のレスポンスを受け取る
                stream=True,
            )
            
            # ストリーミングレスポンスのチャンク単位で処理
            for chunk in stream:
                # チャンク内のコンテンツを取り出す
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    # SSE 形式でデータを送信
                    # data: {JSON形式のメッセージ}\n\n という形式
                    event = {
                        "type": "chunk",
                        "content": content,
                    }
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                    # 送信後に短い遅延を挿入（クライアント側の受信確認用）
                    await asyncio.sleep(0.01)
            
            # ストリーミング完了イベントを送信
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
            
        except asyncio.TimeoutError:
            # タイムアウトエラーをキャッチ
            logger.error(f"Item {item_id} のストリーミング処理がタイムアウトしました")
            error_event = {
                "type": "error",
                "error": "Stream processing timed out",
            }
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
            
        except Exception as exc:
            # その他のエラーをキャッチして詳細をログに記録
            logger.error(f"Item {item_id} のストリーミング中にエラーが発生: {exc}")
            error_event = {
                "type": "error",
                "error": f"Stream processing failed: {str(exc)}",
            }
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
    
    # StreamingResponse で SSE 形式のレスポンスを返す
    # media_type を text/event-stream に設定することで、
    # クライアント側でイベントソースとして受信可能に
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            # ブラウザキャッシュを無効化
            "Cache-Control": "no-cache",
            # CORS 対応
            "X-Accel-Buffering": "no",
        },
    )
