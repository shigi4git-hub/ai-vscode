from pathlib import Path
from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, HTTPException, status      # FastAPIを使えるようにする
from fastapi.responses import FileResponse, JSONResponse  # JSONレスポンスと静的ファイル配信を使用
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from passlib.context import CryptContext
from pydantic import BaseModel, Field   # Fieldを使えるようにする（バリデーションのため）
from jose import ExpiredSignatureError, JWTError, jwt

from database import Session
from models.item import Item
from models.user import User

SECRET_KEY = "secret-key-change-this"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
API_URL = "http://127.0.0.1:8000"

app = FastAPI()                 # APIサーバーを作成
app.mount("/static", StaticFiles(directory="static"), name="static")

# Swagger の Authorize ボタンと OAuth2 認証フローを有効にするための設定
# tokenUrl は Swagger からトークン取得を行うログインエンドポイントを指す
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")  # bcryptでハッシュ化するためのコンテキスト


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def authenticate_user(db, username: str, password: str):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str | None = Depends(oauth2_scheme)):
    """
    OAuth2 の Bearer トークンを検証し、ログイン済みユーザーを返す。
    トークンがない、無効、または期限切れの場合は 401 を返す。
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str | None = payload.get("sub")
    except ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        ) from exc
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        ) from exc

    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    db = Session()
    try:
        user = db.query(User).filter(User.username == username).first()
    finally:
        db.close()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


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

# POST /auth/loginエンドポイント
# Swagger / OAuth2 の Authorize ボタンから送信される標準フォーム形式で受け取る
@app.post("/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    db = Session()
    try:
        # OAuth2PasswordRequestForm では username / password が form_data から取得できる
        db_user = authenticate_user(db, form_data.username, form_data.password)
        if not db_user:
            raise HTTPException(status_code=401, detail="Invalid username or password")

        access_token = create_access_token(data={"sub": db_user.username})
    finally:
        db.close()

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }

# POST /itemsエンドポイント
@app.post("/items")              # POSTリクエストを受け取るURL
def create_item(
    item: ItemCreate,
    current_user: User = Depends(get_current_user),  # ログイン済みユーザーであることを要求
):  # リクエストボディからItemCreateモデルを取得
    # current_user が取得できた時点で認証済みとみなす
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