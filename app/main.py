from pathlib import Path

from fastapi import FastAPI, HTTPException      # FastAPIを使えるようにする
from fastapi.responses import FileResponse, JSONResponse  # JSONレスポンスと静的ファイル配信を使用
from fastapi.staticfiles import StaticFiles
from passlib.context import CryptContext
from pydantic import BaseModel, Field   # Fieldを使えるようにする（バリデーションのため）

from database import Session
from models.item import Item
from models.user import User

API_URL = "http://127.0.0.1:8000"

app = FastAPI()                 # APIサーバーを作成
app.mount("/static", StaticFiles(directory="static"), name="static")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")  # bcryptでハッシュ化するためのコンテキスト

@app.get("/")
def read_root():
    return FileResponse(Path("static") / "index.html")

# アイテム作成用のPydanticモデルを定義
class ItemCreate(BaseModel):
    title: str = Field(min_length=1)    # アイテムのタイトル
    body: str = Field(min_length=1)     # アイテムの内容 
    # Field(min_length=1)を追加して、空の文字列を許可しないようにする

# ユーザー登録用のPydanticモデルを定義
class UserCreate(BaseModel):
    username: str = Field(min_length=1)  # ユーザー名は空文字を許可しない
    password: str = Field(min_length=1)  # パスワードも空文字を許可しない

@app.get("/health")              # GETリクエストを受け取るURL
def health_check():              # そのURLにアクセスされた時に実行される関数
    return {"status": "ok"}     # レスポンスとして返すデータ 

@app.get("/items")
def read_items():
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

# POST /auth/registerエンドポイント
@app.post("/auth/register")
def register_user(user: UserCreate):
    db = Session()
    try:
        existing_user = db.query(User).filter(User.username == user.username).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Username already registered")

        hashed_password = pwd_context.hash(user.password)
        db_user = User(username=user.username, hashed_password=hashed_password)
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
    finally:
        db.close()

    return JSONResponse(
        status_code=201,
        content={
            "message": "User registered",
            "user": {
                "id": db_user.id,
                "username": db_user.username,
            },
        },
    )

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