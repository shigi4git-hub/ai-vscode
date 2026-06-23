from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routers import auth as auth_router
from app.routers import items as items_router
from app.routers import qa as qa_router
from app.routers import feedback as feedback_router

app = FastAPI()  # API サーバーを作成
app.mount("/static", StaticFiles(directory="static"), name="static")

# ルーターを登録して、エンドポイントを分割したモジュールから読み込む。
app.include_router(auth_router.router)
app.include_router(items_router.router)
app.include_router(qa_router.router)
app.include_router(feedback_router.router)


@app.get("/")
def read_root():
    """フロントエンド HTML を返す。"""
    return FileResponse(Path("static") / "index.html")


@app.get("/health")
def health_check():
    """ヘルスチェック用の軽量なエンドポイント。"""
    return {"status": "ok"}
