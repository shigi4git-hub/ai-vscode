from fastapi import FastAPI      # FastAPIを使えるようにする

app = FastAPI()                  # APIサーバーを作成

@app.get("/health")              # GETリクエストを受け取るURL
def health_check():              # そのURLにアクセスされた時に実行される関数
    return {"status": "ok"}     # レスポンスとして返すデータ