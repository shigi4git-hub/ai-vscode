from pathlib import Path

from fastapi import FastAPI      # FastAPIを使えるようにする
from fastapi.responses import FileResponse, JSONResponse  # JSONレスポンスと静的ファイル配信を使用
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field   # Fieldを使えるようにする（バリデーションのため）

from database import Session
from models.item import Item

API_URL = "http://127.0.0.1:8000"

app = FastAPI()                 # APIサーバーを作成
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    return FileResponse(Path("static") / "index.html")

# アイテム作成用のPydanticモデルを定義
class ItemCreate(BaseModel):
    title: str = Field(min_length=1)    # アイテムのタイトル
    body: str = Field(min_length=1)     # アイテムの内容
    # Field(min_length=1)を追加して、空の文字列を許可しないようにする

@app.get("/health")              # GETリクエストを受け取るURL
def health_check():              # そのURLにアクセスされた時に実行される関数
    return {"status": "ok"}     # レスポンスとして返すデータ

# POST /itemsエンドポイント
@app.post("/items")              # POSTリクエストを受け取るURL
def create_item(item: ItemCreate):  # リクエストボディからItemCreateモデルを取得
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