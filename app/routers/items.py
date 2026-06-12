from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from database import Session
from models.item import Item
from models.user import User
from app.dependencies import get_current_user
from app.services.summarize import summarize_text

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
