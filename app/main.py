from fastapi import FastAPI      # FastAPIを使えるようにする
# from pydantic import BaseModel   # Pydanticを使えるようにする
from pydantic import BaseModel, Field   # Fieldを使えるようにする（バリデーションのため）
from fastapi.responses import JSONResponse  # JSONレスポンスを使用

app = FastAPI()                 # APIサーバーを作成

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
    # アイテムを作成してレスポンスを返す
    return JSONResponse(
        status_code=201,         # ステータスコード201（Created）
        content={
            "message": "Item created",  # 作成成功メッセージ
            "item": {                   # 作成されたアイテムを返す
                "title": item.title,
                "body": item.body
            }
        }
    )