from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from database import Session
from models.item import Item
from models.user import User
from app.dependencies import get_current_user

router = APIRouter(prefix="/items", tags=["items"])


class ItemCreate(BaseModel):
    """アイテム作成リクエスト用の入力モデル。"""
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)


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
            }
            for item in items
        ]
    finally:
        db.close()


@router.post("")
def create_item(
    item: ItemCreate,
    current_user: User = Depends(get_current_user),
):
    """認証済みユーザーが新しいアイテムを作成する。"""
    db = Session()
    try:
        db_item = Item(title=item.title, body=item.body)
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
    finally:
        db.close()

    return JSONResponse(
        status_code=201,
        content={
            "message": "Item created",
            "item": {
                "id": db_item.id,
                "title": db_item.title,
                "body": db_item.body,
            },
        },
    )
